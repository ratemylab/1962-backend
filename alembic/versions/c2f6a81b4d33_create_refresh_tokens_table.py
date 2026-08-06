"""create refresh tokens table

Revision ID: c2f6a81b4d33
Revises: 8b1c4e97d520
Create Date: 2026-08-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2f6a81b4d33"
down_revision: Union[str, Sequence[str], None] = "8b1c4e97d520"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("admin_id", sa.String(), nullable=False),
        sa.Column("hashed_refresh_token", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("admin_id", name="uq_refresh_tokens_admin_id"),
    )
    op.create_index(
        "ix_refresh_tokens_hashed_refresh_token",
        "refresh_tokens",
        ["hashed_refresh_token"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_hashed_refresh_token", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
