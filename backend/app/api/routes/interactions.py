from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.routes.leads import owner_key
from app.api.routes.voice import require_local
from app.database import get_session
from app.models.interaction import InteractionSummary
from app.summaries.service import finalise_demo, process

router = APIRouter(prefix="/api/v1/interactions", tags=["interactions"], dependencies=[Depends(require_local)])

class FinaliseInput(BaseModel):
    lead_id: str = Field(min_length=36, max_length=36)
    idempotency_key: str = Field(min_length=16, max_length=80)

def view(item: InteractionSummary, detail: bool = False) -> dict:
    data = {"id": item.id, "customer_display": f"Anonymous {item.customer_id[:8]}",
        "customer_id": item.customer_id, "lead_id": item.lead_id,
        "voice_session_id": item.voice_session_id, "interaction_type": item.interaction_type,
        "started_at": item.started_at, "ended_at": item.ended_at,
        "duration_seconds": item.duration_seconds, "status": item.status,
        "generation_method": item.generation_method, "model_id": item.model_id,
        "lead_classification": (item.structured or {}).get("lead", {}).get("classification"),
        "appointment_status": (item.structured or {}).get("business", {}).get("appointment_status"),
        "summary_text": item.summary_text, "error_code": item.error_code}
    if detail: data["structured"] = item.structured
    return data

@router.post("/demo/finalise", status_code=201)
def finalise(body: FinaliseInput, request: Request, db: Session = Depends(get_session),
             x_voice_owner: str | None = Header(default=None)) -> dict:
    try: item = finalise_demo(db, owner_key(x_voice_owner), body.lead_id, body.idempotency_key, request.app.state.settings)
    except LookupError: raise HTTPException(404, "Lead not found")
    except ValueError as exc: raise HTTPException(409, str(exc))
    return view(item, True)

@router.get("")
def list_interactions(db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None),
                      interaction_type: str | None = None, status: str | None = None,
                      lead_classification: str | None = None, appointment_status: str | None = None,
                      start: date | None = None, end: date | None = None,
                      limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    if start and end and (start > end or (end - start).days > 366): raise HTTPException(422, "Invalid date range")
    query = select(InteractionSummary).where(InteractionSummary.owner_hash == owner_key(x_voice_owner))
    if interaction_type: query = query.where(InteractionSummary.interaction_type == interaction_type.upper())
    if status: query = query.where(InteractionSummary.status == status.upper())
    if lead_classification: query = query.where(InteractionSummary.structured["lead"]["classification"].as_string() == lead_classification.upper())
    if appointment_status: query = query.where(InteractionSummary.structured["business"]["appointment_status"].as_string() == appointment_status.upper())
    if start: query = query.where(InteractionSummary.ended_at >= datetime.combine(start, datetime.min.time(), timezone.utc))
    if end: query = query.where(InteractionSummary.ended_at < datetime.combine(end + timedelta(days=1), datetime.min.time(), timezone.utc))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(InteractionSummary.ended_at.desc()).limit(limit).offset(offset)).all()
    return {"items": [view(item) for item in rows], "total": total, "limit": limit, "offset": offset}

@router.get("/{interaction_id}")
def detail(interaction_id: str, db: Session = Depends(get_session),
           x_voice_owner: str | None = Header(default=None)) -> dict:
    item = db.get(InteractionSummary, interaction_id)
    if not item or item.owner_hash != owner_key(x_voice_owner): raise HTTPException(404, "Interaction not found")
    return view(item, True)

@router.post("/{interaction_id}/retry-summary")
def retry(interaction_id: str, request: Request, db: Session = Depends(get_session),
          x_voice_owner: str | None = Header(default=None)) -> dict:
    item = db.get(InteractionSummary, interaction_id)
    if not item or item.owner_hash != owner_key(x_voice_owner): raise HTTPException(404, "Interaction not found")
    stale = item.status == "PROCESSING" and item.updated_at and (datetime.now(timezone.utc) -
        (item.updated_at.replace(tzinfo=timezone.utc) if item.updated_at.tzinfo is None else item.updated_at)).total_seconds() > 60
    if item.status != "FAILED" and not stale: raise HTTPException(409, "Summary retry not available")
    return view(process(db, item, request.app.state.settings), True)
