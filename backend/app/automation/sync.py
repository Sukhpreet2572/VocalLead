"""Durable, independently tracked provider operations; no silent local fallback."""
from datetime import timedelta
import httpx
from google.auth.exceptions import GoogleAuthError
from requests.exceptions import RequestException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.models.appointment import Appointment, CRMRecord, SyncOperation
from app.models.customer import Customer, Lead, now_utc
from app.models.property import Property
from app.automation.providers import GoogleCalendar, HubSpotCRM, ProviderUnavailable, event_id_for
from app.automation.events import emit
from app.automation.scheduling import aware_utc

def run_operation(db: Session, operation: SyncOperation, settings: Settings) -> None:
    if operation.status == "SYNCED" or operation.attempt_count >= 3: return
    if operation.status == "RECONCILE_REQUIRED": return
    if operation.next_retry_at and aware_utc(operation.next_retry_at) > now_utc(): return
    operation.status = "PENDING"
    operation.attempt_count += 1
    operation.last_attempt_at = now_utc()
    appointment = db.get(Appointment, operation.appointment_id) if operation.appointment_id else None
    record = db.get(CRMRecord, operation.crm_record_id) if operation.crm_record_id else None
    try:
        if operation.provider == "google":
            adapter = GoogleCalendar(settings)
            if operation.operation_type == "CREATE_EVENT":
                if appointment is None: raise ProviderUnavailable("Appointment missing")
                event_id = adapter.create_event(appointment, db.get(Property, appointment.property_id).name)
                appointment.external_event_id = event_id
                appointment.calendar_sync_status = "SYNCED"
                appointment.status = "CONFIRMED"
                crm = db.scalar(select(CRMRecord).where(CRMRecord.customer_id == appointment.customer_id))
                if crm: crm.lifecycle_status = "VISIT_BOOKED"
            elif operation.operation_type == "CANCEL_EVENT":
                if appointment and appointment.external_event_id:
                    adapter.cancel_event(appointment.external_event_id)
                    appointment.calendar_sync_status = "SYNCED"
        elif operation.provider == "hubspot":
            if record is None: raise ProviderUnavailable("CRM record missing")
            customer, lead = db.get(Customer, record.customer_id), db.get(Lead, record.lead_id)
            if not customer.contact_consent or not customer.email:
                record.sync_status = "NOT_REQUIRED"
                record.failure_code = "CONSENT_OR_EMAIL_REQUIRED"
                if appointment: appointment.crm_sync_status = "NOT_REQUIRED"
                operation.status = "NOT_REQUIRED"
                if appointment: emit(db, appointment.owner_hash, "CRM_SYNC_SKIPPED", customer_id=appointment.customer_id,
                                     appointment_id=appointment.id, details={"reason": "CONSENT_OR_EMAIL_REQUIRED"})
                db.commit()
                return
            contact_id = HubSpotCRM(settings).upsert_contact(customer, lead)
            record.external_contact_id = contact_id
            record.sync_status = "SYNCED"
            if appointment: appointment.crm_sync_status = "SYNCED"
            record.last_synced_at = now_utc()
            record.failure_code = None
        operation.status = "SYNCED"
        operation.failure_code = None
    except httpx.TimeoutException:
        # Google creation is reconciled by stable event ID; HubSpot email upsert is safe to retry.
        operation.status = "RECONCILE_REQUIRED" if operation.provider == "google" else "FAILED"
        operation.failure_code = "REMOTE_OUTCOME_UNKNOWN"
        if operation.provider == "hubspot":
            operation.next_retry_at = now_utc() + timedelta(minutes=min(2 ** operation.attempt_count, 30))
        if appointment and operation.provider == "google": appointment.calendar_sync_status = "FAILED"
        if record: record.sync_status = "FAILED"
        if appointment and operation.provider == "hubspot": appointment.crm_sync_status = "FAILED"
    except (ProviderUnavailable, httpx.HTTPError, GoogleAuthError, RequestException, ValueError, KeyError, OSError):
        operation.status = "FAILED"
        operation.failure_code = "PROVIDER_UNAVAILABLE"
        operation.next_retry_at = now_utc() + timedelta(minutes=min(2 ** operation.attempt_count, 30))
        if appointment and operation.provider == "google": appointment.calendar_sync_status = "FAILED"
        if record:
            record.sync_status = "FAILED"
            record.failure_code = operation.failure_code
            record.retry_count = operation.attempt_count
        if appointment and operation.provider == "hubspot": appointment.crm_sync_status = "FAILED"
    if appointment:
        emit(db, appointment.owner_hash, f"{operation.provider.upper()}_SYNC_{operation.status}",
             customer_id=appointment.customer_id, appointment_id=appointment.id, session_id=appointment.session_id,
             details={"operation": operation.operation_type, "failure_code": operation.failure_code})
    db.commit()

def sync_appointment(db: Session, appointment_id: str, settings: Settings) -> None:
    operations = db.scalars(select(SyncOperation).where(SyncOperation.appointment_id == appointment_id,
        SyncOperation.status == "PENDING")).all()
    for operation in operations:
        run_operation(db, operation, settings)

def reconcile_calendar(db: Session, appointment: Appointment, operation: SyncOperation, settings: Settings) -> None:
    if operation.status != "RECONCILE_REQUIRED": return
    try:
        event = GoogleCalendar(settings).get_event(event_id_for(appointment.id))
    except (ProviderUnavailable, httpx.HTTPError, GoogleAuthError, RequestException, ValueError, OSError):
        raise ProviderUnavailable("Calendar reconciliation unavailable")
    if event and event.get("status") != "cancelled":
        appointment.external_event_id = event_id_for(appointment.id)
        appointment.status = "CONFIRMED"
        appointment.calendar_sync_status = "SYNCED"
        crm = db.scalar(select(CRMRecord).where(CRMRecord.customer_id == appointment.customer_id))
        if crm: crm.lifecycle_status = "VISIT_BOOKED"
        operation.status = "SYNCED"
        operation.failure_code = None
    else:
        operation.status = "FAILED"
        operation.next_retry_at = now_utc()
        operation.failure_code = "EVENT_NOT_FOUND"
        appointment.calendar_sync_status = "FAILED"
    emit(db, appointment.owner_hash, "GOOGLE_SYNC_RECONCILED", customer_id=appointment.customer_id,
         appointment_id=appointment.id, details={"status": operation.status})
    db.commit()
