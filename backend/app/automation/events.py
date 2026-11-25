"""Small durable business activity log with no transcript or contact fields."""
from uuid import uuid4
from sqlalchemy.orm import Session
from app.models.appointment import BusinessEvent

def emit(db: Session, owner_hash: str, event_type: str, *, customer_id: str | None = None,
         appointment_id: str | None = None, session_id: str | None = None,
         details: dict | None = None) -> None:
    db.add(BusinessEvent(id=str(uuid4()), owner_hash=owner_hash, event_type=event_type,
                         customer_id=customer_id, appointment_id=appointment_id,
                         session_id=session_id, details=details or {}))
