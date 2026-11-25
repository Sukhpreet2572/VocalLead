from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    preferred_language: Mapped[str] = mapped_column(String(12), default="en", nullable=False)
    contact_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    contact_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False, unique=True)
    customer: Mapped[Customer] = relationship()
    location: Mapped[str | None] = mapped_column(String(100))
    property_type: Mapped[str | None] = mapped_column(String(30))
    configuration: Mapped[str | None] = mapped_column(String(30))
    min_budget_inr: Mapped[int | None] = mapped_column(Integer)
    max_budget_inr: Mapped[int | None] = mapped_column(Integer)
    timeline_months: Mapped[int | None] = mapped_column(Integer)
    purchase_intent: Mapped[str | None] = mapped_column(String(20))
    ready_to_move: Mapped[bool | None] = mapped_column(Boolean)
    interested_property_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    site_visit_interest: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    classification: Mapped[str] = mapped_column(String(10), default="COLD", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="NEW", nullable=False)
    sentiment: Mapped[str] = mapped_column(String(10), default="UNKNOWN", nullable=False)
    business_signal: Mapped[str] = mapped_column(String(30), default="UNSPECIFIED", nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(250), default="Ask about property needs.", nullable=False)
    score_components: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    facts_provenance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    objections: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    unresolved_questions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
    __table_args__ = (Index("ix_leads_classification", "classification"), Index("ix_leads_status", "status"),)


class LeadScoreHistory(Base):
    __tablename__ = "lead_score_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("voice_sessions.id"))
    previous_score: Mapped[int] = mapped_column(Integer, nullable=False)
    new_score: Mapped[int] = mapped_column(Integer, nullable=False)
    components: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(250), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class CustomerMemory(Base):
    __tablename__ = "customer_memories"
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), primary_key=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("voice_sessions.id"))
    facts: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    unresolved_questions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    objections: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    last_interaction_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
