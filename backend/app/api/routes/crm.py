from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.routes.leads import owner_key
from app.api.routes.voice import require_local
from app.automation.sync import run_operation
from app.automation.scheduling import aware_utc
from app.models.customer import now_utc
from app.database import get_session
from app.models.appointment import CRMRecord, SyncOperation
from app.models.customer import Customer

router = APIRouter(prefix="/api/v1/crm", tags=["crm"], dependencies=[Depends(require_local)])

def view(record: CRMRecord) -> dict:
    return {"id": record.id, "customer_id": record.customer_id, "lead_id": record.lead_id,
            "provider": record.provider, "lifecycle_status": record.lifecycle_status,
            "sync_status": record.sync_status, "last_synced_at": record.last_synced_at,
            "failure_code": record.failure_code, "retry_count": record.retry_count,
            "external_contact_id": record.external_contact_id}

@router.get("/records")
def records(db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None),
            limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    key = owner_key(x_voice_owner)
    query = select(CRMRecord).join(Customer).where(Customer.owner_hash == key)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(CRMRecord.updated_at.desc()).limit(limit).offset(offset)).all()
    return {"items": [view(item) for item in items], "total": total}

@router.post("/records/{record_id}/sync")
def sync_record(record_id: str, request: Request, db: Session = Depends(get_session),
                x_voice_owner: str | None = Header(default=None)) -> dict:
    key = owner_key(x_voice_owner)
    record = db.scalar(select(CRMRecord).join(Customer).where(CRMRecord.id == record_id, Customer.owner_hash == key))
    if not record: raise HTTPException(404, "CRM record not found")
    if record.provider != "hubspot": raise HTTPException(409, "Local CRM does not need external synchronisation")
    operation = db.scalar(select(SyncOperation).where(SyncOperation.crm_record_id == record.id,
        SyncOperation.operation_type == "UPSERT_CONTACT"))
    if not operation: raise HTTPException(409, "No CRM synchronisation operation")
    if operation.status == "RECONCILE_REQUIRED": raise HTTPException(409, "Reconcile remote outcome before retry")
    if operation.attempt_count >= 3: raise HTTPException(409, "Retry limit reached")
    if operation.next_retry_at and aware_utc(operation.next_retry_at) > now_utc():
        raise HTTPException(409, "Retry window not reached")
    run_operation(db, operation, request.app.state.settings)
    db.refresh(record)
    return view(record)
