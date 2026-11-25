from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VoiceSession(Base):
    __tablename__ = "voice_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    room_name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    participant_identity: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    owner_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="CREATED")
    consent_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False)
    consent_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    failure_reason: Mapped[str | None] = mapped_column(String(120))
    dispatch_id: Mapped[str | None] = mapped_column(String(80))
