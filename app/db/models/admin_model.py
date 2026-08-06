from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base_model import Base


class AdminDB(Base):
    """Administrator account authenticated with a username, password and JWT."""

    __tablename__ = "admins"
    __table_args__ = (UniqueConstraint("username", name="uq_admins_username"),)

    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
