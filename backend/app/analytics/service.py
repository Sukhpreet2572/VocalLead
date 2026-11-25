"""Owner-scoped, record-based business metrics. No inferred revenue or sales claims."""
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.models.appointment import Appointment, BookingProposal, CRMRecord, SyncOperation, BusinessEvent
from app.models.customer import Customer, Lead
from app.models.interaction import InteractionSummary
from app.models.voice_session import VoiceSession

def bounds(start: date | None, end: date | None) -> tuple[datetime | None, datetime | None]:
    return (datetime.combine(start, time.min, timezone.utc) if start else None,
            datetime.combine(end + timedelta(days=1), time.min, timezone.utc) if end else None)

def within(stmt, column, start, end):
    low, high = bounds(start, end)
    if low: stmt = stmt.where(column >= low)
    if high: stmt = stmt.where(column < high)
    return stmt

def counts(values) -> list[dict]:
    counter = Counter(value for value in values if value is not None)
    return [{"label": key, "count": value} for key, value in sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))]

def metrics(db: Session, owner_hash: str, start: date | None = None, end: date | None = None) -> dict:
    leads = db.scalars(within(select(Lead).join(Customer).where(Customer.owner_hash == owner_hash),
                              Lead.created_at, start, end)).all()
    interactions = db.scalars(within(select(InteractionSummary).where(InteractionSummary.owner_hash == owner_hash),
                                     InteractionSummary.ended_at, start, end)).all()
    voices = db.scalars(within(select(VoiceSession).where(VoiceSession.owner_hash == owner_hash),
                               VoiceSession.created_at, start, end)).all()
    appointments = db.scalars(within(select(Appointment).where(Appointment.owner_hash == owner_hash),
                                     Appointment.created_at, start, end)).all()
    proposals = db.scalars(within(select(BookingProposal).where(BookingProposal.owner_hash == owner_hash),
                                  BookingProposal.created_at, start, end)).all()
    crm = db.scalars(within(select(CRMRecord).join(Customer).where(Customer.owner_hash == owner_hash),
                            CRMRecord.created_at, start, end)).all()
    lead_ids = {lead.id for lead in leads}
    confirmed_leads = {item.lead_id for item in appointments if item.status == "CONFIRMED" and item.lead_id in lead_ids}
    measured = [item.duration_seconds for item in voices if item.status == "COMPLETED" and item.duration_seconds is not None]
    volume = Counter(item.ended_at.date().isoformat() for item in interactions)
    known_scores = [item.score for item in leads]
    budget_buckets = Counter()
    for lead in leads:
        if lead.max_budget_inr is None: budget_buckets["Unknown"] += 1
        elif lead.max_budget_inr < 10_000_000: budget_buckets["Under 1 crore"] += 1
        elif lead.max_budget_inr <= 20_000_000: budget_buckets["1–2 crore"] += 1
        else: budget_buckets["Over 2 crore"] += 1
    appointment_ids = {item.id for item in appointments}
    crm_ids = {item.id for item in crm}
    operations = db.scalars(select(SyncOperation).where(or_(SyncOperation.appointment_id.in_(appointment_ids),
        SyncOperation.crm_record_id.in_(crm_ids)))).all() if appointment_ids or crm_ids else []
    lead_metrics = {"total": len(leads), "hot": sum(item.classification == "HOT" for item in leads),
        "warm": sum(item.classification == "WARM" for item in leads),
        "cold": sum(item.classification == "COLD" for item in leads),
        "insufficient_information": sum(not (item.location and item.configuration and item.max_budget_inr) for item in leads),
        "average_score": round(sum(known_scores) / len(known_scores), 1) if known_scores else None,
        "hot_percentage": round(100 * sum(item.classification == "HOT" for item in leads) / len(leads), 1) if leads else None,
        "classification_distribution": counts(item.classification for item in leads)}
    appointment_metrics = {"proposals": len(proposals),
        "confirmed": sum(item.status == "CONFIRMED" for item in appointments),
        "cancelled": sum(item.status == "CANCELLED" for item in appointments),
        "completed": sum(item.status == "COMPLETED" for item in appointments),
        "upcoming": sum(item.status == "CONFIRMED" and (item.start_at.replace(tzinfo=timezone.utc) if item.start_at.tzinfo is None else item.start_at) > datetime.now(timezone.utc) for item in appointments),
        "leads_with_confirmed_appointments": len(confirmed_leads),
        "conversion_rate": round(100 * len(confirmed_leads) / len(leads), 1) if leads else None,
        "conversion_definition": "Distinct selected-cohort leads with a confirmed appointment created in the date range / selected-cohort leads created in the date range; not property sales conversion.",
        "status_distribution": counts(item.status for item in appointments)}
    interaction_metrics = {"total": len(interactions),
        "completed_voice_calls": sum(item.status == "COMPLETED" for item in voices),
        "local_demo_interactions": sum(item.interaction_type == "LOCAL_DEMO" for item in interactions),
        "failed_voice_sessions": sum(item.status == "FAILED" for item in voices),
        "average_voice_duration_seconds": round(sum(measured) / len(measured), 1) if measured else None,
        "summary_completion_rate": round(100 * sum(item.status == "COMPLETED" for item in interactions) / len(interactions), 1) if interactions else None,
        "volume_by_day": [{"date": key, "count": value} for key, value in sorted(volume.items())],
        "type_distribution": counts(item.interaction_type for item in interactions)}
    property_demand = {"interested_property_ids": counts(property_id for lead in leads for property_id in (lead.interested_property_ids or [])),
        "locations": counts(item.location for item in leads),
        "configurations": counts(item.configuration for item in leads),
        "budget_buckets": [{"label": key, "count": value} for key, value in budget_buckets.items()]}
    intelligence = {"sentiment": counts(item.sentiment or "UNKNOWN" for item in leads),
        "unknown_sentiment": sum(item.sentiment in (None, "UNKNOWN") for item in leads),
        "objections": counts(objection for lead in leads for objection in (lead.objections or [])),
        "languages": counts(lead.customer.preferred_language for lead in leads),
        "timeline_months": counts(str(lead.timeline_months) if lead.timeline_months is not None else "Unknown" for lead in leads)}
    integration = {"calendar_sync": counts(item.calendar_sync_status for item in appointments),
        "crm_sync": counts(item.sync_status for item in crm),
        "failed_operations": sum(item.status in ("FAILED", "RECONCILE_REQUIRED") for item in operations),
        "pending_operations": sum(item.status == "PENDING" for item in operations)}
    qualified_without_visit = sum(lead.classification in ("HOT", "WARM") and lead.id not in confirmed_leads for lead in leads)
    insights = []
    if qualified_without_visit: insights.append(f"{qualified_without_visit} qualified leads in this cohort have no confirmed site visit in the selected period.")
    if integration["failed_operations"]: insights.append(f"{integration['failed_operations']} external synchronisation operations need review.")
    if not interaction_metrics["completed_voice_calls"]: insights.append("No completed voice calls are recorded in this period.")
    if len(leads) >= 3 and property_demand["configurations"]:
        top = property_demand["configurations"][0]
        if top["count"] >= 3: insights.append(f"{top['label']} is the most recorded configuration ({top['count']} leads).")
    return {"interactions": interaction_metrics, "leads": lead_metrics, "appointments": appointment_metrics,
            "property_demand": property_demand, "customer_intelligence": intelligence,
            "integrations": integration, "insights": {"method": "DETERMINISTIC", "items": insights}}
