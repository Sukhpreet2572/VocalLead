"""Voice business tools use trusted session ownership; browser handles final confirmation."""
import asyncio
import json
from datetime import date, datetime
from livekit.agents import function_tool
from sqlalchemy import select
from app.automation.scheduling import available_slots, propose
from app.core.config import Settings
from app.database import build_engine, session_factory
from app.models.appointment import Appointment
from app.models.customer import Lead
from app.models.voice_session import VoiceSession

def _context(session_id: str):
    engine = build_engine(Settings())
    db = session_factory(engine)()
    voice = db.get(VoiceSession, session_id)
    if not voice or not voice.customer_id:
        db.close(); engine.dispose(); raise LookupError("Customer session unavailable")
    lead = db.scalar(select(Lead).where(Lead.customer_id == voice.customer_id))
    if not lead:
        db.close(); engine.dispose(); raise LookupError("Lead unavailable")
    return engine, db, voice, lead

def _check(session_id: str, property_id: str, day: str) -> str:
    engine, db, _, _ = _context(session_id)
    try:
        slots = available_slots(db, property_id, date.fromisoformat(day), Settings())
        return json.dumps([{"start_at": slot["start_at"].isoformat(), "local_display": slot["local_display"]} for slot in slots[:8]])
    finally:
        db.close(); engine.dispose()

def _propose(session_id: str, property_id: str, start_at: str) -> str:
    engine, db, voice, lead = _context(session_id)
    try:
        item = propose(db, voice.owner_hash, lead.id, property_id, datetime.fromisoformat(start_at), Settings(), session_id)
        return json.dumps({"proposal_id": item.id, "start_at": item.start_at.isoformat(),
                           "expires_at": item.expires_at.isoformat(), "status": "PENDING_CUSTOMER_CONFIRMATION"})
    finally:
        db.close(); engine.dispose()

def _status(session_id: str, appointment_id: str) -> str:
    engine, db, voice, _ = _context(session_id)
    try:
        item = db.get(Appointment, appointment_id)
        if not item or item.customer_id != voice.customer_id or item.owner_hash != voice.owner_hash:
            return "Appointment not found"
        return json.dumps({"id": item.id, "status": item.status,
                           "calendar_sync_status": item.calendar_sync_status, "crm_sync_status": item.crm_sync_status})
    finally:
        db.close(); engine.dispose()

def tools_for_session(session_id: str):
    @function_tool
    async def check_appointment_availability(property_id: str, day: str) -> str:
        """Check genuine site visit slots for a property and ISO date, e.g. 2026-12-01."""
        try: return await asyncio.to_thread(_check, session_id, property_id, day)
        except Exception: return "Availability unavailable; do not invent slots."

    @function_tool
    async def propose_appointment(property_id: str, start_at: str) -> str:
        """Create a pending site visit proposal for an ISO timestamp with timezone. This does not book it."""
        try: return await asyncio.to_thread(_propose, session_id, property_id, start_at)
        except Exception: return "Proposal unavailable; offer human assistance."

    @function_tool
    async def get_appointment_status(appointment_id: str) -> str:
        """Read the actual appointment and independent calendar/CRM status for this customer."""
        try: return await asyncio.to_thread(_status, session_id, appointment_id)
        except Exception: return "Appointment status unavailable."

    return [check_appointment_availability, propose_appointment, get_appointment_status]
