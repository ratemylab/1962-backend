from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base_model import Base


class TicketDB(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("ticket_id", name="uq_tickets_ticket_id"),
        Index("ix_tickets_ticket_id", "ticket_id"),
        Index("ix_tickets_client_id", "client_id"),
        Index("ix_tickets_ticket_status", "ticket_status"),
    )

    ticket_id: Mapped[str] = mapped_column(String(50), nullable=False)
    client_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ticket_status: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_date_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_date_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    farmer_id: Mapped[str] = mapped_column(String(20), nullable=False)
    farmer_name: Mapped[str] = mapped_column(String(100), nullable=False)

    village_id: Mapped[int] = mapped_column(nullable=False)
    village: Mapped[str] = mapped_column(String(100), nullable=False)
    panchayat_id: Mapped[int] = mapped_column(nullable=False)
    panchayat: Mapped[str] = mapped_column(String(100), nullable=False)
    block_id: Mapped[int] = mapped_column(nullable=False)
    block: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)

    disease: Mapped[str] = mapped_column(String(200), nullable=False)
    symptoms: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    treatment_given: Mapped[str | None] = mapped_column(String, nullable=True)

    doctor_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    doctor_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paravet_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    paravet_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mvu_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    client: Mapped["ClientDB"] = relationship("ClientDB", back_populates="tickets")
    animals: Mapped[list["AnimalDB"]] = relationship(
        "AnimalDB",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )
    audio_file: Mapped["AudioFileDB | None"] = relationship(
        "AudioFileDB",
        back_populates="ticket",
        cascade="all, delete-orphan",
        uselist=False,
    )
