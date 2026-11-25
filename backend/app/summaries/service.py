"""Idempotent, record-grounded interaction summaries without transcript storage."""
import hashlib
from datetime import timezone
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.automation.events import emit
from app.core.config import Settings
from app.models.appointment import Appointment, BookingProposal, CRMRecord
from app.models.customer import Customer, Lead, now_utc
from app.models.interaction import InteractionSummary
from app.models.property import Property
from app.models.voice_session import VoiceSession
from app.summaries.provider import gemini_narrative
from app.summaries.schemas import (BusinessSnapshot, ConversationSnapshot, LeadSnapshot,
    RequirementsSnapshot, StructuredSummary, SummaryMetadata)

def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def build_summary(db: Session, item: InteractionSummary) -> StructuredSummary:
    lead = db.get(Lead, item.lead_id)
    if lead is None: raise ValueError("Lead unavailable")
    requirements = RequirementsSnapshot(location=lead.location, configuration=lead.configuration,
        max_budget_inr=lead.max_budget_inr, timeline_months=lead.timeline_months,
        property_type=lead.property_type, ready_to_move=lead.ready_to_move)
    known = sum(value is not None for value in (lead.location, lead.configuration, lead.max_budget_inr, lead.timeline_months))
    objective = None
    if lead.configuration or lead.location:
        objective = "Seeking " + " ".join(x for x in (lead.configuration, "property" if lead.configuration else None,
                             "in " + lead.location if lead.location else None) if x)
    conversation = ConversationSnapshot(main_objective=objective,
        discussed_property_ids=list(lead.interested_property_ids or []),
        unresolved_questions=list(lead.unresolved_questions or []), objections=list(lead.objections or []),
        sentiment=lead.sentiment or "UNKNOWN")
    qualification = LeadSnapshot(score=lead.score, classification=lead.classification,
        components=lead.score_components or {}, purchase_intent=lead.purchase_intent,
        recommended_follow_up=lead.recommended_action)
    proposal = db.scalar(select(BookingProposal).where(BookingProposal.customer_id == item.customer_id,
        BookingProposal.created_at <= item.ended_at).order_by(BookingProposal.created_at.desc()))
    appointment = db.scalar(select(Appointment).where(Appointment.customer_id == item.customer_id,
        Appointment.created_at <= item.ended_at).order_by(Appointment.created_at.desc()))
    crm = db.scalar(select(CRMRecord).where(CRMRecord.customer_id == item.customer_id))
    business = BusinessSnapshot(proposal_status=proposal.status if proposal else None,
        appointment_status=appointment.status if appointment else None,
        appointment_id=appointment.id if appointment else None,
        calendar_sync_status=appointment.calendar_sync_status if appointment else None,
        crm_lifecycle_status=crm.lifecycle_status if crm else None,
        crm_sync_status=crm.sync_status if crm else None)
    phrases = []
    if objective: phrases.append(objective + ".")
    else: phrases.append("Customer property requirements are unavailable.")
    if lead.max_budget_inr is not None: phrases.append(f"Maximum budget is INR {lead.max_budget_inr:,}.")
    if lead.timeline_months is not None: phrases.append(f"Purchase timeline is {lead.timeline_months} months.")
    phrases.append(f"Recorded lead score is {lead.score}/100 ({lead.classification}).")
    if appointment:
        property_item = db.get(Property, appointment.property_id)
        phrases.append(f"Site visit {appointment.status.lower()} for {property_item.name if property_item else appointment.property_id}; calendar sync {appointment.calendar_sync_status}, CRM sync {appointment.crm_sync_status}.")
    elif proposal:
        phrases.append(f"Latest appointment proposal is {proposal.status.lower()}; no confirmed appointment is recorded.")
    if crm: phrases.append(f"Local CRM lifecycle is {crm.lifecycle_status}.")
    if lead.objections: phrases.append("Recorded objections: " + "; ".join(lead.objections[:5]) + ".")
    if lead.sentiment and lead.sentiment != "UNKNOWN": phrases.append(f"Latest recorded text sentiment is {lead.sentiment}.")
    limitations = ["Record-based summary; no transcript was stored or reviewed."]
    if item.interaction_type == "LOCAL_DEMO": limitations.append("Synthetic local demonstration, not a voice call.")
    if lead.sentiment in (None, "UNKNOWN"): limitations.append("Customer sentiment is unknown.")
    metadata = SummaryMetadata(interaction_type=item.interaction_type, generation_method="DETERMINISTIC",
        generated_at=now_utc(), data_completeness="LIMITED" if known < 2 else "PARTIAL" if known < 4 else "SUBSTANTIAL",
        limitations=limitations)
    return StructuredSummary(requirements=requirements, conversation=conversation, lead=qualification,
        business=business, metadata=metadata, summary_text=" ".join(phrases))

def process(db: Session, item: InteractionSummary, settings: Settings,
            transient_text: str | None = None) -> InteractionSummary:
    if item.status == "COMPLETED": return item
    item.status = "PROCESSING"
    item.error_code = None
    emit(db, item.owner_hash, "SUMMARY_PROCESSING_STARTED", customer_id=item.customer_id,
         session_id=item.voice_session_id, details={"interaction_id": item.id})
    db.commit()
    try:
        summary = build_summary(db, item)
        if item.interaction_type == "VOICE" and transient_text and settings.voice_transcript_retention_enabled and settings.google_api_key.get_secret_value():
            try:
                narrative = gemini_narrative(summary, settings, transient_text)
                summary.summary_text = narrative.summary_text
                summary.metadata.generation_method = "LLM"
                summary.metadata.model_id = settings.gemini_model or "gemini-2.5-flash"
                summary.metadata.limitations = [x for x in summary.metadata.limitations if not x.startswith("Record-based")]
                summary.metadata.limitations.append("Business identifiers, score and provider statuses come from database records.")
            except Exception:
                item.error_code = "LLM_UNAVAILABLE_DETERMINISTIC_USED"
        validated = StructuredSummary.model_validate(summary.model_dump())
        item.structured = validated.model_dump(mode="json")
        item.summary_text = validated.summary_text
        item.generation_method = validated.metadata.generation_method
        item.model_id = validated.metadata.model_id
        item.generated_at = validated.metadata.generated_at
        item.status = "COMPLETED"
        emit(db, item.owner_hash, "SUMMARY_GENERATED", customer_id=item.customer_id,
             session_id=item.voice_session_id, details={"interaction_id": item.id, "method": item.generation_method})
    except Exception:
        item.status = "FAILED"
        item.error_code = "SUMMARY_PROCESSING_FAILED"
        emit(db, item.owner_hash, "SUMMARY_PROCESSING_FAILED", customer_id=item.customer_id,
             session_id=item.voice_session_id, details={"interaction_id": item.id})
    db.commit(); db.refresh(item)
    return item

def finalise_demo(db: Session, owner_hash: str, lead_id: str, idempotency_key: str,
                  settings: Settings) -> InteractionSummary:
    if len(idempotency_key) < 16 or len(idempotency_key) > 80:
        raise ValueError("Invalid idempotency key")
    source = "demo:" + hashlib.sha256(f"{owner_hash}:{idempotency_key}".encode()).hexdigest()
    existing = db.scalar(select(InteractionSummary).where(InteractionSummary.source_key == source))
    if existing:
        if existing.owner_hash != owner_hash or existing.lead_id != lead_id:
            raise ValueError("Idempotency key reused for a different interaction")
        return process(db, existing, settings) if existing.status == "FAILED" else existing
    lead = db.scalar(select(Lead).join(Customer).where(Lead.id == lead_id, Customer.owner_hash == owner_hash))
    if not lead: raise LookupError("Lead not found")
    item = InteractionSummary(id=str(uuid4()), owner_hash=owner_hash, source_key=source,
        voice_session_id=None, customer_id=lead.customer_id, lead_id=lead.id, interaction_type="LOCAL_DEMO",
        started_at=None, ended_at=now_utc(), duration_seconds=None, status="PENDING")
    db.add(item)
    emit(db, owner_hash, "INTERACTION_FINALISED", customer_id=lead.customer_id,
         details={"interaction_id": item.id, "interaction_type": "LOCAL_DEMO"})
    try: db.commit()
    except IntegrityError:
        db.rollback()
        same = db.scalar(select(InteractionSummary).where(InteractionSummary.source_key == source))
        if same and same.owner_hash == owner_hash and same.lead_id == lead_id: return same
        raise ValueError("Idempotency key reused for a different interaction")
    return process(db, item, settings)

def finalise_voice(db: Session, voice_session_id: str, settings: Settings,
                   transient_text: str | None = None) -> InteractionSummary | None:
    voice = db.get(VoiceSession, voice_session_id)
    if not voice or voice.status != "COMPLETED" or not voice.customer_id: return None
    source = f"voice:{voice.id}"
    item = db.scalar(select(InteractionSummary).where(InteractionSummary.source_key == source))
    if item is None:
        lead = db.scalar(select(Lead).where(Lead.customer_id == voice.customer_id))
        if lead is None: return None
        item = InteractionSummary(id=str(uuid4()), owner_hash=voice.owner_hash, source_key=source,
            voice_session_id=voice.id, customer_id=voice.customer_id, lead_id=lead.id, interaction_type="VOICE",
            started_at=voice.started_at, ended_at=voice.ended_at or now_utc(),
            duration_seconds=voice.duration_seconds, status="PENDING")
        db.add(item)
        emit(db, voice.owner_hash, "INTERACTION_FINALISED", customer_id=voice.customer_id,
             session_id=voice.id, details={"interaction_id": item.id, "interaction_type": "VOICE"})
        try: db.commit()
        except IntegrityError:
            db.rollback()
            item = db.scalar(select(InteractionSummary).where(InteractionSummary.source_key == source))
            if item is None: raise
    if item.status == "PROCESSING": return item
    return process(db, item, settings, transient_text)
