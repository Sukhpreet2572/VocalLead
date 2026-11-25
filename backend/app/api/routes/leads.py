"""Owner-bound local demo customer intelligence endpoints."""
import secrets
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.routes.voice import owner_hash, require_local
from app.database import get_session
from app.intelligence.schemas import MessageInput, ProfileUpdate
from app.intelligence.service import create_demo_customer, parse_message, sentiment, update_profile
from app.intelligence.provider import extract_with_gemini, sentiment_with_gemini
from app.models.customer import Customer, Lead, LeadScoreHistory

router = APIRouter(prefix="/api/v1/leads", tags=["leads"], dependencies=[Depends(require_local)])

def owner_key(raw: str | None) -> str:
    if not raw or len(raw) < 32:
        raise HTTPException(403, "Demo owner key is required")
    return owner_hash(raw)

def owned_lead(db: Session, lead_id: str, key: str) -> Lead:
    lead = db.scalar(select(Lead).join(Customer).where(Lead.id == lead_id, Customer.owner_hash == key))
    if not lead: raise HTTPException(404, "Lead not found")
    return lead

def view(lead: Lead) -> dict:
    customer = lead.customer
    return {"id": lead.id, "customer_id": customer.id, "customer_display": customer.display_name or f"Anonymous {customer.id[:8]}",
            "preferred_language": customer.preferred_language, "contact_consent": customer.contact_consent,
            "location": lead.location, "property_type": lead.property_type, "configuration": lead.configuration,
            "min_budget_inr": lead.min_budget_inr, "max_budget_inr": lead.max_budget_inr,
            "timeline_months": lead.timeline_months, "purchase_intent": lead.purchase_intent,
            "ready_to_move": lead.ready_to_move, "interested_property_ids": lead.interested_property_ids,
            "site_visit_interest": lead.site_visit_interest, "score": lead.score,
            "classification": lead.classification, "status": lead.status, "sentiment": lead.sentiment,
            "business_signal": lead.business_signal, "recommended_action": lead.recommended_action,
            "score_components": lead.score_components, "updated_at": lead.updated_at}

@router.get("/summary")
def summary(db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None)) -> dict:
    key = owner_key(x_voice_owner)
    leads = db.scalars(select(Lead).join(Customer).where(Customer.owner_hash == key)).all()
    return {"total": len(leads), "hot": sum(x.classification == "HOT" for x in leads),
            "warm": sum(x.classification == "WARM" for x in leads), "cold": sum(x.classification == "COLD" for x in leads),
            "insufficient_information": sum(not (x.location and x.configuration and x.max_budget_inr) for x in leads)}

@router.get("")
def list_leads(db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None),
               classification: str | None = None, status: str | None = None, location: str | None = None,
               sentiment: str | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    key = owner_key(x_voice_owner)
    stmt = select(Lead).join(Customer).where(Customer.owner_hash == key)
    if classification: stmt = stmt.where(Lead.classification == classification.upper())
    if status: stmt = stmt.where(Lead.status == status.upper())
    if location: stmt = stmt.where(Lead.location.ilike(f"%{location[:100]}%"))
    if sentiment: stmt = stmt.where(Lead.sentiment == sentiment.upper())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Lead.updated_at.desc()).limit(limit).offset(offset)).all()
    return {"items": [view(row) for row in rows], "total": total, "limit": limit, "offset": offset}

@router.post("/demo", status_code=201)
def create_demo(db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None)) -> dict:
    customer, lead = create_demo_customer(db, owner_key(x_voice_owner))
    return {**view(lead), "customer_id": customer.id}

@router.get("/{lead_id}")
def detail(lead_id: str, db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None)) -> dict:
    lead = owned_lead(db, lead_id, owner_key(x_voice_owner))
    history = db.scalars(select(LeadScoreHistory).where(LeadScoreHistory.lead_id == lead.id)
                         .order_by(LeadScoreHistory.created_at.desc()).limit(25)).all()
    return {**view(lead), "score_history": [{"previous_score": item.previous_score, "new_score": item.new_score,
             "components": item.components, "reason": item.reason, "created_at": item.created_at} for item in history]}

@router.patch("/{lead_id}")
def patch_lead(lead_id: str, body: ProfileUpdate, db: Session = Depends(get_session),
               x_voice_owner: str | None = Header(default=None)) -> dict:
    lead = owned_lead(db, lead_id, owner_key(x_voice_owner))
    try: update_profile(db, lead.customer, lead, body)
    except ValueError: raise HTTPException(422, "Invalid requirements")
    return view(lead)

@router.post("/{lead_id}/messages")
def message(lead_id: str, body: MessageInput, request: Request, db: Session = Depends(get_session),
            x_voice_owner: str | None = Header(default=None)) -> dict:
    lead = owned_lead(db, lead_id, owner_key(x_voice_owner))
    settings = request.app.state.settings
    has_provider = bool(settings.google_api_key.get_secret_value())
    try:
        update = extract_with_gemini(body.message, settings) if has_provider else parse_message(body.message)
        result = sentiment_with_gemini(body.message, settings) if has_provider else None
    except Exception:
        raise HTTPException(503, "Customer intelligence provider unavailable")
    try: update_profile(db, lead.customer, lead, update, source="deterministic_phrase_parser")
    except ValueError: raise HTTPException(422, "Invalid requirements")
    label, signal, mode = (result.sentiment, result.business_signal, "gemini_structured") if result else sentiment(body.message)
    lead.sentiment, lead.business_signal = label, signal
    db.commit()
    return {"lead": view(lead), "extraction_mode": "gemini_structured" if has_provider else "deterministic_phrase_parser", "sentiment_mode": mode,
            "extracted_fields": list(update.model_dump(exclude_unset=True, exclude_none=True))}
