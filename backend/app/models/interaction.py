from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.customer import now_utc


class InteractionSummary(Base):
    __tablename__ = "interaction_summaries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    voice_session_id: Mapped[str | None] = mapped_column(ForeignKey("voice_sessions.id"), unique=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), nullable=False)
    interaction_type: Mapped[str] = mapped_column(String(15), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(15), default="PENDING", nullable=False)
    generation_method: Mapped[str | None] = mapped_column(String(20))
    model_id: Mapped[str | None] = mapped_column(String(100))
    structured: Mapped[dict | None] = mapped_column(JSON)
    summary_text: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(80))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
    __table_args__ = (Index("ix_interactions_owner_ended", "owner_hash", "ended_at"),)
