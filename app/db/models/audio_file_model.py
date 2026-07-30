from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base_model import Base


class AudioFileDB(Base):
    __tablename__ = "audio_files"
    __table_args__ = (
        UniqueConstraint("ticket_id", name="uq_audio_files_ticket_id"),
        UniqueConstraint("audio_file_id", name="uq_audio_files_audio_file_id"),
        Index("ix_audio_files_ticket_id", "ticket_id"),
        Index("ix_audio_files_client_id", "client_id"),
        Index("ix_audio_files_audio_file_id", "audio_file_id"),
    )

    ticket_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    client_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    audio_file_id: Mapped[str] = mapped_column(String(50), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )

    ticket: Mapped["TicketDB"] = relationship("TicketDB", back_populates="audio_file")
    client: Mapped["ClientDB"] = relationship("ClientDB", back_populates="audio_files")
