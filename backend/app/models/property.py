from sqlalchemy import ForeignKey, Integer, String, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Property(Base):
    __tablename__ = "properties"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    location: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    possession: Mapped[str] = mapped_column(String(80), nullable=False)
    amenities: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    connectivity: Mapped[str] = mapped_column(String(250), nullable=False)
    payment: Mapped[str] = mapped_column(String(250), nullable=False)
    units: Mapped[list["PropertyUnit"]] = relationship(back_populates="property", cascade="all, delete-orphan")


class PropertyUnit(Base):
    __tablename__ = "property_units"
    __table_args__ = (UniqueConstraint("property_id", "configuration"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), nullable=False, index=True)
    configuration: Mapped[str] = mapped_column(String(30), nullable=False)
    price_inr: Mapped[int] = mapped_column(Integer, nullable=False)
    carpet_sqft: Mapped[int] = mapped_column(Integer, nullable=False)
    available: Mapped[int] = mapped_column(Integer, nullable=False)
    property: Mapped[Property] = relationship(back_populates="units")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    source: Mapped[str] = mapped_column(String(250), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    property_id: Mapped[str | None] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
