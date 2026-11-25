from datetime import date, datetime
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.routes.leads import owner_key
from app.api.routes.voice import require_local
from app.automation.scheduling import available_slots, aware_utc, cancel, confirm, propose
from app.automation.sync import run_operation, sync_appointment, reconcile_calendar
from app.automation.providers import ProviderUnavailable
from app.database import get_session
from app.models.appointment import Appointment, BookingProposal, CRMRecord, SyncOperation, BusinessEvent
from app.automation.events import emit
from app.models.customer import Customer, now_utc
from app.models.property import Property

router = APIRouter(prefix="/api/v1/appointments", tags=["appointments"], dependencies=[Depends(require_local)])

class ProposalInput(BaseModel):
    lead_id: str = Field(min_length=36, max_length=36)
    property_id: str = Field(min_length=1, max_length=64)
    start_at: datetime

class ConfirmationInput(BaseModel):
    proposal_id: str = Field(min_length=36, max_length=36)
    idempotency_key: str = Field(min_length=16, max_length=80)
    explicit_confirmation: bool

def appointment_view(db: Session, item: Appointment) -> dict:
    customer = db.get(Customer, item.customer_id)
    property_item = db.get(Property, item.property_id)
    operations = db.scalars(select(SyncOperation).where(SyncOperation.appointment_id == item.id)).all()
    return {"id": item.id, "customer_id": item.customer_id,
            "customer_display": customer.display_name or f"Anonymous {customer.id[:8]}",
            "lead_id": item.lead_id, "property_id": item.property_id, "property_name": property_item.name,
            "start_at": item.start_at, "end_at": item.end_at, "timezone": item.timezone,
            "status": item.status, "booking_provider": item.booking_provider,
            "calendar_sync_status": item.calendar_sync_status, "crm_sync_status": item.crm_sync_status,
            "external_event_id": item.external_event_id, "failure_code": item.failure_code,
            "operations": [{"type": op.operation_type, "provider": op.provider, "status": op.status,
                            "attempts": op.attempt_count, "failure_code": op.failure_code} for op in operations]}

def owned(db: Session, appointment_id: str, key: str) -> Appointment:
    item = db.get(Appointment, appointment_id)
    if item is None or item.owner_hash != key: raise HTTPException(404, "Appointment not found")
    return item

@router.get("/summary")
def summary(db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None)) -> dict:
    items = db.scalars(select(Appointment).where(Appointment.owner_hash == owner_key(x_voice_owner))).all()
    now = now_utc()
    return {"upcoming": sum(x.status == "CONFIRMED" and aware_utc(x.start_at) > now for x in items),
            "confirmed": sum(x.status == "CONFIRMED" for x in items),
            "cancelled": sum(x.status == "CANCELLED" for x in items),
            "pending_sync": sum(x.calendar_sync_status == "PENDING" or x.crm_sync_status == "PENDING" for x in items),
            "failed_sync": sum(x.calendar_sync_status == "FAILED" or x.crm_sync_status == "FAILED" for x in items)}

@router.get("/availability")
def availability(request: Request, property_id: str, day: date, db: Session = Depends(get_session),
                 x_voice_owner: str | None = Header(default=None)) -> dict:
    key = owner_key(x_voice_owner)
    emit(db, key, "APPOINTMENT_AVAILABILITY_REQUESTED", details={"property_id": property_id, "day": day.isoformat()})
    db.commit()
    try:
        slots = available_slots(db, property_id, day, request.app.state.settings)
    except ValueError as exc: raise HTTPException(422, str(exc))
    except Exception: raise HTTPException(503, "Calendar availability unavailable")
    emit(db, key, "AVAILABLE_SLOTS_RETRIEVED", details={"property_id": property_id, "day": day.isoformat(), "count": len(slots)})
    db.commit()
    return {"property_id": property_id, "day": day, "slots": slots, "provider": request.app.state.settings.calendar_provider}

@router.get("/activity")
def activity(db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None),
             limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    key = owner_key(x_voice_owner)
    rows = db.scalars(select(BusinessEvent).where(BusinessEvent.owner_hash == key)
                      .order_by(BusinessEvent.created_at.desc()).limit(limit).offset(offset)).all()
    return {"items": [{"event_type": row.event_type, "appointment_id": row.appointment_id,
                        "session_id": row.session_id, "details": row.details, "created_at": row.created_at} for row in rows]}

@router.get("/proposals")
def pending_proposals(db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None),
                      limit: int = Query(20, ge=1, le=100)) -> dict:
    key = owner_key(x_voice_owner)
    rows = db.scalars(select(BookingProposal).where(BookingProposal.owner_hash == key,
        BookingProposal.status == "PENDING", BookingProposal.expires_at > now_utc())
        .order_by(BookingProposal.created_at.desc()).limit(limit)).all()
    return {"items": [{"id": row.id, "customer_id": row.customer_id, "lead_id": row.lead_id,
                        "property_id": row.property_id, "property_name": db.get(Property, row.property_id).name,
                        "start_at": row.start_at, "end_at": row.end_at, "timezone": row.timezone,
                        "expires_at": row.expires_at, "status": row.status} for row in rows]}

@router.post("/proposals", status_code=201)
def create_proposal(body: ProposalInput, request: Request, db: Session = Depends(get_session),
                    x_voice_owner: str | None = Header(default=None)) -> dict:
    try:
        item = propose(db, owner_key(x_voice_owner), body.lead_id, body.property_id,
                       body.start_at, request.app.state.settings)
    except LookupError: raise HTTPException(404, "Lead not found")
    except ValueError as exc: raise HTTPException(422, str(exc))
    except Exception: raise HTTPException(503, "Calendar availability unavailable")
    return {"id": item.id, "customer_id": item.customer_id, "lead_id": item.lead_id,
            "property_id": item.property_id, "start_at": item.start_at, "end_at": item.end_at,
            "timezone": item.timezone, "status": item.status, "expires_at": item.expires_at}

@router.post("/confirm")
def confirm_proposal(body: ConfirmationInput, request: Request, db: Session = Depends(get_session),
                     x_voice_owner: str | None = Header(default=None)) -> dict:
    try:
        item = confirm(db, owner_key(x_voice_owner), body.proposal_id, body.idempotency_key,
                       body.explicit_confirmation, request.app.state.settings)
    except LookupError: raise HTTPException(404, "Proposal not found")
    except ValueError as exc: raise HTTPException(409, str(exc))
    sync_appointment(db, item.id, request.app.state.settings)
    db.refresh(item)
    return appointment_view(db, item)

@router.get("")
def list_appointments(db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None),
                      limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    key = owner_key(x_voice_owner)
    query = select(Appointment).where(Appointment.owner_hash == key)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(Appointment.start_at.desc()).limit(limit).offset(offset)).all()
    return {"items": [appointment_view(db, item) for item in items], "total": total, "limit": limit, "offset": offset}

@router.get("/{appointment_id}")
def detail(appointment_id: str, db: Session = Depends(get_session),
           x_voice_owner: str | None = Header(default=None)) -> dict:
    return appointment_view(db, owned(db, appointment_id, owner_key(x_voice_owner)))

@router.post("/{appointment_id}/cancel")
def cancel_appointment(appointment_id: str, request: Request, db: Session = Depends(get_session),
                       x_voice_owner: str | None = Header(default=None)) -> dict:
    item = cancel(db, owned(db, appointment_id, owner_key(x_voice_owner)))
    for operation in db.scalars(select(SyncOperation).where(SyncOperation.appointment_id == item.id,
        SyncOperation.operation_type == "CANCEL_EVENT", SyncOperation.status == "PENDING")).all():
        run_operation(db, operation, request.app.state.settings)
    db.refresh(item)
    return appointment_view(db, item)

@router.post("/{appointment_id}/sync")
def retry_calendar(appointment_id: str, request: Request, db: Session = Depends(get_session),
                   x_voice_owner: str | None = Header(default=None)) -> dict:
    item = owned(db, appointment_id, owner_key(x_voice_owner))
    if item.booking_provider != "google": raise HTTPException(409, "Local calendar needs no external synchronisation")
    operation = db.scalar(select(SyncOperation).where(SyncOperation.appointment_id == item.id,
        SyncOperation.provider == "google", SyncOperation.operation_type == "CREATE_EVENT"))
    if not operation: raise HTTPException(409, "No calendar synchronisation operation")
    if operation.status == "RECONCILE_REQUIRED": raise HTTPException(409, "Reconcile remote outcome before retry")
    if operation.attempt_count >= 3: raise HTTPException(409, "Retry limit reached")
    if operation.next_retry_at and aware_utc(operation.next_retry_at) > now_utc():
        raise HTTPException(409, "Retry window not reached")
    run_operation(db, operation, request.app.state.settings)
    db.refresh(item)
    return appointment_view(db, item)

@router.post("/{appointment_id}/reconcile")
def reconcile(appointment_id: str, request: Request, db: Session = Depends(get_session),
              x_voice_owner: str | None = Header(default=None)) -> dict:
    item = owned(db, appointment_id, owner_key(x_voice_owner))
    operation = db.scalar(select(SyncOperation).where(SyncOperation.appointment_id == item.id,
        SyncOperation.provider == "google", SyncOperation.operation_type == "CREATE_EVENT"))
    if not operation or operation.status != "RECONCILE_REQUIRED":
        raise HTTPException(409, "No ambiguous Calendar operation")
    try: reconcile_calendar(db, item, operation, request.app.state.settings)
    except ProviderUnavailable: raise HTTPException(503, "Calendar reconciliation unavailable")
    db.refresh(item)
    return appointment_view(db, item)
