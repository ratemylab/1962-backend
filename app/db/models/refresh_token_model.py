from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base_model import Base


class RefreshTokenDB(Base):
    """Opaque refresh token issued to an admin at login.

    The unique constraint on admin_id enforces a single active session: logging
    in again replaces the row, so the previous refresh token stops working.
    Only the hash is stored, exactly as for client API tokens.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        UniqueConstraint("admin_id", name="uq_refresh_tokens_admin_id"),
        Index("ix_refresh_tokens_hashed_refresh_token", "hashed_refresh_token"),
    )

    admin_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=False,
    )
    hashed_refresh_token: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
