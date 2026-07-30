from __future__ import annotations

from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base_model import Base


class ClientDB(Base):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("client_id", name="uq_clients_client_id"),
        Index("ix_clients_client_id", "client_id"),
    )

    client_id: Mapped[str] = mapped_column(String(100), nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_token: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tickets: Mapped[list["TicketDB"]] = relationship("TicketDB", back_populates="client")
    audio_files: Mapped[list["AudioFileDB"]] = relationship("AudioFileDB", back_populates="client")
