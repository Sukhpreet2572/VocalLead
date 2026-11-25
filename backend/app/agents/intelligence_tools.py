"""Per-call tools bind customer identity to trusted dispatch metadata."""
import asyncio
import json
from livekit.agents import function_tool
from sqlalchemy import select
from app.core.config import Settings
from app.database import build_engine, session_factory
from app.intelligence.schemas import ProfileUpdate
from app.intelligence.service import parse_message, sentiment, update_profile
from app.intelligence.provider import extract_with_gemini, sentiment_with_gemini
from app.models.customer import Customer, Lead, CustomerMemory
from app.models.voice_session import VoiceSession

def _operate(session_id: str, operation: str, payload: str = "") -> str:
    engine = build_engine(Settings())
    try:
        with session_factory(engine)() as db:
            voice = db.get(VoiceSession, session_id)
            if not voice or not voice.customer_id: return "No customer context is bound to this session."
            customer = db.get(Customer, voice.customer_id)
            lead = db.scalar(select(Lead).where(Lead.customer_id == voice.customer_id))
            if not customer or not lead or customer.owner_hash != voice.owner_hash: return "Customer context unavailable."
            if operation == "get":
                memory = db.get(CustomerMemory, customer.id)
                return json.dumps({"facts": memory.facts if memory else {}, "score": lead.score,
                    "classification": lead.classification, "sentiment": lead.sentiment,
                    "signal": lead.business_signal, "action": lead.recommended_action}, ensure_ascii=False)
            if operation == "update":
                update = ProfileUpdate.model_validate(json.loads(payload))
                update_profile(db, customer, lead, update, source="agent_tool", session_id=session_id)
            elif operation == "message":
                settings = Settings()
                provider = bool(settings.google_api_key.get_secret_value())
                update = extract_with_gemini(payload, settings) if provider else parse_message(payload)
                result = sentiment_with_gemini(payload, settings) if provider else None
                update_profile(db, customer, lead, update, source="gemini_structured" if provider else "deterministic_phrase_parser", session_id=session_id)
                if provider:
                    lead.sentiment, lead.business_signal = result.sentiment, result.business_signal
                else:
                    lead.sentiment, lead.business_signal, _ = sentiment(payload)
                db.commit()
            return json.dumps({"score": lead.score, "classification": lead.classification,
                               "components": lead.score_components, "next_action": lead.recommended_action}, ensure_ascii=False)
    finally:
        engine.dispose()

def tools_for_session(session_id: str):
    @function_tool
    async def get_customer_context() -> str:
        """Read verified structured customer facts and current qualification for this call."""
        return await asyncio.to_thread(_operate, session_id, "get")

    @function_tool
    async def update_customer_requirements(profile_json: str) -> str:
        """Save explicitly stated facts. JSON keys include location, configuration, max_budget_inr, timeline_months, purchase_intent, site_visit_interest. Never invent missing fields."""
        try: return await asyncio.to_thread(_operate, session_id, "update", profile_json)
        except (ValueError, TypeError): return "Invalid profile update; ask the customer to clarify."

    @function_tool
    async def calculate_lead_score() -> str:
        """Read the deterministic score and component reasons from stored evidence."""
        return await asyncio.to_thread(_operate, session_id, "get")

    @function_tool
    async def analyze_customer_message(final_message: str) -> str:
        """Apply limited deterministic parsing and text business signals to a final customer turn."""
        try: return await asyncio.to_thread(_operate, session_id, "message", final_message)
        except (ValueError, TypeError): return "Could not parse this message."

    return [get_customer_context, update_customer_requirements, calculate_lead_score, analyze_customer_message]
