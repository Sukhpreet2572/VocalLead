from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.customer import now_utc


class BookingProposal(Base):
    __tablename__ = "booking_proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), nullable=False)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("voice_sessions.id"))
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(40), nullable=False)
    appointment_type: Mapped[str] = mapped_column(String(30), default="SITE_VISIT", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), nullable=False)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("voice_sessions.id"))
    proposal_id: Mapped[str] = mapped_column(ForeignKey("booking_proposals.id"), nullable=False, unique=True)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(40), nullable=False)
    appointment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="CONFIRMED", nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    booking_provider: Mapped[str] = mapped_column(String(20), nullable=False)
    external_event_id: Mapped[str | None] = mapped_column(String(120))
    calendar_sync_status: Mapped[str] = mapped_column(String(20), nullable=False)
    crm_sync_status: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
    __table_args__ = (Index("ix_appointments_owner_start", "owner_hash", "start_at"),)


class SlotReservation(Base):
    __tablename__ = "slot_reservations"
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), primary_key=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id"), nullable=False, unique=True)


class CRMRecord(Base):
    __tablename__ = "crm_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False, unique=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    external_contact_id: Mapped[str | None] = mapped_column(String(120))
    lifecycle_status: Mapped[str] = mapped_column(String(30), default="NEW", nullable=False)
    sync_status: Mapped[str] = mapped_column(String(20), default="NOT_CONFIGURED", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class SyncOperation(Base):
    __tablename__ = "sync_operations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    operation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    appointment_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.id"))
    crm_record_id: Mapped[str | None] = mapped_column(ForeignKey("crm_records.id"))
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class BusinessEvent(Base):
    __tablename__ = "business_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("voice_sessions.id"))
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"))
    appointment_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.id"))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (Index("ix_business_events_owner_created", "owner_hash", "created_at"),)
