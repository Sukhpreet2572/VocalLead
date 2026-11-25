"""Local appointment rules and transactional reservations."""
import hashlib
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.models.appointment import Appointment, BookingProposal, CRMRecord, SlotReservation, SyncOperation
from app.models.customer import Customer, Lead, now_utc
from app.models.property import Property
from app.automation.events import emit

TZ = ZoneInfo("Asia/Kolkata")
OPEN_HOUR, CLOSE_HOUR = 10, 17  # Tuesday-Sunday, matching synthetic policy.

def aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def property_ready(db: Session, property_id: str) -> Property:
    property_item = db.get(Property, property_id)
    if not property_item or property_item.status not in ("ready", "under_construction") or not any(u.available > 0 for u in property_item.units):
        raise ValueError("Property unavailable for visits")
    return property_item

def available_slots(db: Session, property_id: str, day: date, settings: Settings,
                    now: datetime | None = None, external_busy: list[tuple[datetime, datetime]] | None = None) -> list[dict]:
    property_ready(db, property_id)
    current = aware_utc(now or now_utc())
    local_today = current.astimezone(TZ).date()
    if day < local_today or day > local_today + timedelta(days=settings.appointment_booking_horizon_days):
        raise ValueError("Date outside booking horizon")
    if day.weekday() == 0: return []
    duration = timedelta(minutes=settings.appointment_duration_minutes)
    if 60 % settings.appointment_duration_minutes != 0:
        raise ValueError("Duration must align to the hour")
    reserved = {aware_utc(row.start_at) for row in db.scalars(select(SlotReservation).where(SlotReservation.property_id == property_id)).all()}
    if settings.calendar_provider == "google" and external_busy is None:
        from app.automation.providers import GoogleCalendar
        opening = datetime.combine(day, time(OPEN_HOUR), TZ).astimezone(timezone.utc)
        closing_utc = datetime.combine(day, time(CLOSE_HOUR), TZ).astimezone(timezone.utc)
        external_busy = GoogleCalendar(settings).busy(opening, closing_utc)
    slots = []
    at = datetime.combine(day, time(OPEN_HOUR), TZ)
    closing = datetime.combine(day, time(CLOSE_HOUR), TZ)
    while at + duration <= closing:
        start, end = at.astimezone(timezone.utc), (at + duration).astimezone(timezone.utc)
        if (start >= current + timedelta(minutes=settings.appointment_min_notice_minutes) and start not in reserved and
            not any(start < aware_utc(busy_end) and end > aware_utc(busy_start) for busy_start, busy_end in (external_busy or []))):
            slots.append({"property_id": property_id, "start_at": start, "end_at": end,
                          "local_display": at.strftime("%a %d %b %Y, %I:%M %p IST"),
                          "availability_provider": settings.calendar_provider,
                          "expires_at": (current + timedelta(seconds=settings.booking_proposal_ttl_seconds))})
        at += duration
    return slots

def owned_lead(db: Session, lead_id: str, owner_hash: str) -> Lead:
    lead = db.scalar(select(Lead).join(Customer).where(Lead.id == lead_id, Customer.owner_hash == owner_hash))
    if lead is None: raise LookupError("Lead not found")
    return lead

def propose(db: Session, owner_hash: str, lead_id: str, property_id: str, start_at: datetime,
            settings: Settings, session_id: str | None = None, now: datetime | None = None) -> BookingProposal:
    if start_at.tzinfo is None: raise ValueError("Timezone offset required")
    lead = owned_lead(db, lead_id, owner_hash)
    if session_id:
        from app.models.voice_session import VoiceSession
        voice = db.get(VoiceSession, session_id)
        if not voice or voice.owner_hash != owner_hash or voice.customer_id != lead.customer_id:
            raise LookupError("Voice session not found")
    start = start_at.astimezone(timezone.utc)
    slot = next((s for s in available_slots(db, property_id, start.astimezone(TZ).date(), settings, now)
                 if s["start_at"] == start), None)
    if slot is None: raise ValueError("Slot unavailable")
    proposal = BookingProposal(id=str(uuid4()), owner_hash=owner_hash, customer_id=lead.customer_id,
        lead_id=lead.id, session_id=session_id, property_id=property_id, start_at=start, end_at=slot["end_at"],
        timezone=settings.appointment_timezone, expires_at=slot["expires_at"], status="PENDING")
    db.add(proposal); db.commit(); db.refresh(proposal)
    emit(db, owner_hash, "BOOKING_PROPOSAL_CREATED", customer_id=lead.customer_id,
         session_id=session_id, details={"proposal_id": proposal.id, "property_id": property_id})
    db.commit()
    return proposal

def local_crm(db: Session, lead: Lead, provider: str) -> CRMRecord:
    record = db.scalar(select(CRMRecord).where(CRMRecord.customer_id == lead.customer_id))
    if record is None:
        record = CRMRecord(id=str(uuid4()), customer_id=lead.customer_id, lead_id=lead.id,
                           provider=provider, lifecycle_status="NEW",
                           sync_status="NOT_REQUIRED" if provider == "local" else "PENDING")
        db.add(record)
    return record

def confirm(db: Session, owner_hash: str, proposal_id: str, key: str, explicit: bool,
            settings: Settings, now: datetime | None = None) -> Appointment:
    if not explicit: raise ValueError("Explicit confirmation required")
    if not 16 <= len(key) <= 80: raise ValueError("Invalid idempotency key")
    digest = hashlib.sha256(f"{owner_hash}:{key}".encode()).hexdigest()
    existing = db.scalar(select(Appointment).where(Appointment.idempotency_key == digest))
    if existing:
        if existing.owner_hash != owner_hash or existing.proposal_id != proposal_id:
            raise ValueError("Idempotency key reused for a different booking")
        return existing
    proposal = db.get(BookingProposal, proposal_id)
    if not proposal or proposal.owner_hash != owner_hash: raise LookupError("Proposal not found")
    current = aware_utc(now or now_utc())
    if proposal.status != "PENDING" or aware_utc(proposal.expires_at) <= current:
        raise ValueError("Proposal expired or already used")
    slot = next((s for s in available_slots(db, proposal.property_id, aware_utc(proposal.start_at).astimezone(TZ).date(), settings, current)
                 if s["start_at"] == aware_utc(proposal.start_at)), None)
    if slot is None:
        emit(db, owner_hash, "APPOINTMENT_CONFLICT_DETECTED", customer_id=proposal.customer_id,
             session_id=proposal.session_id, details={"property_id": proposal.property_id})
        db.commit()
        raise ValueError("Slot no longer available")
    lead = owned_lead(db, proposal.lead_id, owner_hash)
    emit(db, owner_hash, "BOOKING_VALIDATION_COMPLETED", customer_id=proposal.customer_id,
         session_id=proposal.session_id, details={"proposal_id": proposal.id})
    appt = Appointment(id=str(uuid4()), owner_hash=owner_hash, customer_id=proposal.customer_id,
        lead_id=proposal.lead_id, session_id=proposal.session_id, proposal_id=proposal.id,
        property_id=proposal.property_id, start_at=proposal.start_at, end_at=proposal.end_at,
        timezone=proposal.timezone, appointment_type=proposal.appointment_type,
        status="CONFIRMED" if settings.calendar_provider == "local" else "PENDING",
        booking_provider=settings.calendar_provider, calendar_sync_status="NOT_REQUIRED" if settings.calendar_provider == "local" else "PENDING",
        crm_sync_status="NOT_REQUIRED" if settings.crm_provider == "local" else "PENDING", idempotency_key=digest)
    db.add(appt)
    db.add(SlotReservation(property_id=proposal.property_id, start_at=proposal.start_at, appointment_id=appt.id))
    proposal.status = "CONFIRMED"
    emit(db, owner_hash, "CUSTOMER_CONFIRMATION_RECEIVED", customer_id=proposal.customer_id,
         appointment_id=appt.id, session_id=proposal.session_id)
    with db.no_autoflush:
        record = local_crm(db, lead, settings.crm_provider)
    record.lifecycle_status = "VISIT_BOOKED" if settings.calendar_provider == "local" else "VISIT_REQUESTED"
    emit(db, owner_hash, "CRM_RECORD_UPDATED", customer_id=proposal.customer_id,
         appointment_id=appt.id, details={"lifecycle_status": record.lifecycle_status})
    if settings.calendar_provider == "google":
        db.add(SyncOperation(id=str(uuid4()), operation_type="CREATE_EVENT", appointment_id=appt.id,
            provider="google", idempotency_key=f"event:{appt.id}", status="PENDING"))
    if settings.crm_provider == "hubspot":
        db.add(SyncOperation(id=str(uuid4()), operation_type="UPSERT_CONTACT", appointment_id=appt.id,
            crm_record_id=record.id, provider="hubspot", idempotency_key=f"contact:{record.id}", status="PENDING"))
    emit(db, owner_hash, "APPOINTMENT_CONFIRMED" if settings.calendar_provider == "local" else "APPOINTMENT_PENDING_CALENDAR",
         customer_id=proposal.customer_id, appointment_id=appt.id, session_id=proposal.session_id,
         details={"property_id": proposal.property_id})
    try:
        db.commit(); db.refresh(appt)
    except (IntegrityError, OperationalError):
        db.rollback()
        same = db.scalar(select(Appointment).where(Appointment.idempotency_key == digest))
        if same and same.proposal_id == proposal_id and same.owner_hash == owner_hash: return same
        emit(db, owner_hash, "APPOINTMENT_CONFLICT_DETECTED", customer_id=proposal.customer_id,
             session_id=proposal.session_id, details={"property_id": proposal.property_id})
        db.commit()
        raise ValueError("Slot was booked concurrently")
    return appt

def cancel(db: Session, appt: Appointment) -> Appointment:
    if appt.status == "CANCELLED": return appt
    appt.status, appt.cancelled_at = "CANCELLED", now_utc()
    reservation = db.scalar(select(SlotReservation).where(SlotReservation.appointment_id == appt.id))
    if reservation: db.delete(reservation)
    record = db.scalar(select(CRMRecord).where(CRMRecord.customer_id == appt.customer_id))
    if record: record.lifecycle_status = "QUALIFIED" if record.lifecycle_status == "VISIT_BOOKED" else record.lifecycle_status
    if appt.booking_provider == "google" and appt.external_event_id:
        db.add(SyncOperation(id=str(uuid4()), operation_type="CANCEL_EVENT", appointment_id=appt.id,
            provider="google", idempotency_key=f"cancel:{appt.id}", status="PENDING"))
        appt.calendar_sync_status = "PENDING"
    emit(db, appt.owner_hash, "APPOINTMENT_CANCELLED", customer_id=appt.customer_id,
         appointment_id=appt.id, session_id=appt.session_id)
    db.commit(); db.refresh(appt)
    return appt
