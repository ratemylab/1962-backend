from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base_model import Base


class AnimalDB(Base):
    __tablename__ = "animals"
    __table_args__ = (
        Index("ix_animals_ticket_id", "ticket_id"),
    )

    ticket_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    animal_name: Mapped[str] = mapped_column(String(50), nullable=False)
    breed_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    ticket: Mapped["TicketDB"] = relationship("TicketDB", back_populates="animals")
