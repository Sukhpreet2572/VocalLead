"""Shared deterministic customer intelligence service. No transcript storage."""
import re
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.customer import Customer, Lead, LeadScoreHistory, CustomerMemory, now_utc
from app.models.property import PropertyUnit
from app.intelligence.schemas import ProfileUpdate

WEIGHTS = {"inventory_match": 30, "strong_intent": 25, "within_three_months": 20,
           "site_visit": 15, "valid_contact": 10}

def parse_budget(text: str) -> int | None:
    lower = text.casefold().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(crore|cr|करोड़)(?:\s*(\d+(?:\.\d+)?)\s*(lakh|lac|लाख))?", lower)
    if match:
        return int(float(match[1]) * 10_000_000 + (float(match[3]) * 100_000 if match[3] else 0))
    match = re.search(r"(\d+(?:\.\d+)?)\s*(lakh|lac|लाख)", lower)
    return int(float(match[1]) * 100_000) if match else None

def parse_message(text: str) -> ProfileUpdate:
    """Narrow, explicitly deterministic fallback for clearly stated facts only."""
    lower = text.casefold()
    data: dict = {}
    budget = parse_budget(text)
    if budget and any(word in lower for word in ("budget", "maximum", "max", "under", "within", "upto", "up to", "stretch", "तक", "बजट")):
        data["max_budget_inr"] = budget
    configuration = re.search(r"\b([1-6])\s*bhk\b", lower)
    if configuration: data["configuration"] = f"{configuration[1]} BHK"
    if any(word in lower for word in ("gurgaon", "gurugram", "गुरुग्राम", "गुड़गांव")):
        data["location"] = "Gurugram"
    if re.search(r"\b(?:within|in)\s+(\d+)\s+months?\b", lower):
        data["timeline_months"] = int(re.search(r"\b(?:within|in)\s+(\d+)\s+months?\b", lower)[1])
    if any(phrase in lower for phrase in ("book a visit", "site visit", "visit the property")):
        data["site_visit_interest"] = True
    if any(phrase in lower for phrase in ("ready to buy", "want to purchase", "will buy")):
        data["purchase_intent"] = "STRONG"
    if any(phrase in lower for phrase in ("not interested", "don't contact", "do not contact")):
        data["purchase_intent"] = "NOT_INTERESTED"
    return ProfileUpdate.model_validate(data)

def sentiment(text: str) -> tuple[str, str, str]:
    lower = text.casefold()
    signals = [("NOT_INTERESTED", "NEGATIVE", ("not interested", "don't contact")),
               ("FRUSTRATED", "NEGATIVE", ("frustrated", "annoyed", "stop calling")),
               ("PRICE_CONCERN", "MIXED", ("too expensive", "costly", "over budget")),
               ("CONFUSED", "UNKNOWN", ("confused", "don't understand")),
               ("READY_TO_PROCEED", "POSITIVE", ("ready to buy", "book a visit")),
               ("INTERESTED", "POSITIVE", ("interested", "like this property"))]
    for signal, label, words in signals:
        if any(word in lower for word in words): return label, signal, "deterministic_phrase_fallback"
    return "UNKNOWN", "UNSPECIFIED", "deterministic_phrase_fallback"

def score_lead(db: Session, customer: Customer, lead: Lead) -> tuple[int, dict]:
    match = False
    if lead.max_budget_inr and lead.configuration and lead.location:
        for unit in db.scalars(select(PropertyUnit)).all():
            if (unit.available > 0 and unit.price_inr <= lead.max_budget_inr and
                (lead.min_budget_inr is None or unit.price_inr >= lead.min_budget_inr) and
                unit.configuration.casefold() == lead.configuration.casefold() and
                lead.location.casefold() in unit.property.location.casefold() and
                (lead.property_type is None or lead.property_type.casefold() == unit.property.type.casefold())):
                match = True; break
    awarded = {"inventory_match": match, "strong_intent": lead.purchase_intent == "STRONG",
               "within_three_months": lead.timeline_months is not None and lead.timeline_months <= 3,
               "site_visit": lead.site_visit_interest is True,
               "valid_contact": bool(customer.phone or customer.email) and customer.contact_consent}
    reasons = {"inventory_match": "Available matching unit within budget", "strong_intent": "Explicit strong purchase intent",
               "within_three_months": "Confirmed timeline within three months", "site_visit": "Explicit site visit interest",
               "valid_contact": "Voluntary valid contact with consent"}
    components = {key: {"points": WEIGHTS[key] if yes else 0, "reason": reasons[key] if yes else f"No verified {key.replace('_', ' ')} evidence"}
                  for key, yes in awarded.items()}
    return sum(item["points"] for item in components.values()), components

def update_profile(db: Session, customer: Customer, lead: Lead, update: ProfileUpdate,
                   source: str = "structured", session_id: str | None = None) -> Lead:
    values = update.model_dump(exclude_unset=True, exclude_none=True)
    if "min_budget_inr" in values and "max_budget_inr" in values and values["min_budget_inr"] > values["max_budget_inr"]:
        raise ValueError("Minimum budget exceeds maximum budget")
    provenance = dict(lead.facts_provenance or {})
    for key, value in values.items():
        target = customer if key in {"display_name", "phone", "email", "preferred_language", "contact_consent"} else lead
        setattr(target, key, value)
        provenance[key] = {"source": source, "at": now_utc().isoformat()}
    if values.get("contact_consent") is True: customer.contact_consent_at = now_utc()
    if values.get("contact_consent") is False: customer.contact_consent_at = None
    lead.facts_provenance = provenance
    previous = lead.score
    lead.score, lead.score_components = score_lead(db, customer, lead)
    lead.classification = "HOT" if lead.score >= 75 else "WARM" if lead.score >= 45 else "COLD"
    lead.recommended_action = ("Respect the customer's decision." if lead.purchase_intent == "NOT_INTERESTED" else
        "Offer a site visit or sales consultation; no booking is made." if lead.classification == "HOT" else
        "Show matching properties and clarify timeline." if lead.classification == "WARM" else
        "Ask a relevant discovery question without pressure.")
    if previous != lead.score:
        db.add(LeadScoreHistory(id=str(uuid4()), lead_id=lead.id, session_id=session_id,
                                previous_score=previous, new_score=lead.score,
                                components=lead.score_components, reason="Profile evidence changed"))
    memory = db.get(CustomerMemory, customer.id)
    if memory is None:
        memory = CustomerMemory(customer_id=customer.id, facts={}, unresolved_questions=[], objections=[])
        db.add(memory)
    memory.facts = {key: getattr(lead if hasattr(lead, key) else customer, key) for key in provenance
                    if key not in {"phone", "email", "display_name"}}
    memory.session_id = session_id
    memory.last_interaction_at = now_utc()
    db.commit()
    db.refresh(lead)
    return lead

def create_demo_customer(db: Session, owner_hash: str) -> tuple[Customer, Lead]:
    customer = Customer(id=str(uuid4()), owner_hash=owner_hash)
    lead = Lead(id=str(uuid4()), customer_id=customer.id, customer=customer)
    db.add_all([customer, lead]); db.commit()
    return customer, lead
