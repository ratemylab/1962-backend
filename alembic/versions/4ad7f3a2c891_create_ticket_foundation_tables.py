"""create ticket foundation tables

Revision ID: 4ad7f3a2c891
Revises:
Create Date: 2026-07-22 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "4ad7f3a2c891"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("client_id", sa.String(length=100), nullable=False),
        sa.Column("client_name", sa.String(length=255), nullable=False),
        sa.Column("hashed_token", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", name="uq_clients_client_id"),
    )
    op.create_index("ix_clients_client_id", "clients", ["client_id"], unique=False)

    op.create_table(
        "tickets",
        sa.Column("ticket_id", sa.String(length=50), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("ticket_status", sa.String(length=50), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("created_date_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_date_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("farmer_id", sa.String(length=20), nullable=False),
        sa.Column("farmer_name", sa.String(length=100), nullable=False),
        sa.Column("village_id", sa.Integer(), nullable=False),
        sa.Column("village", sa.String(length=100), nullable=False),
        sa.Column("panchayat_id", sa.Integer(), nullable=False),
        sa.Column("panchayat", sa.String(length=100), nullable=False),
        sa.Column("block_id", sa.Integer(), nullable=False),
        sa.Column("block", sa.String(length=100), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("disease", sa.String(length=200), nullable=False),
        sa.Column("symptoms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("treatment_given", sa.String(), nullable=True),
        sa.Column("doctor_id", sa.String(length=20), nullable=True),
        sa.Column("doctor_name", sa.String(length=100), nullable=True),
        sa.Column("paravet_id", sa.String(length=20), nullable=True),
        sa.Column("paravet_name", sa.String(length=100), nullable=True),
        sa.Column("mvu_number", sa.String(length=20), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id", name="uq_tickets_ticket_id"),
    )
    op.create_index("ix_tickets_client_id", "tickets", ["client_id"], unique=False)
    op.create_index("ix_tickets_ticket_id", "tickets", ["ticket_id"], unique=False)
    op.create_index("ix_tickets_ticket_status", "tickets", ["ticket_status"], unique=False)

    op.create_table(
        "animals",
        sa.Column("ticket_id", sa.String(), nullable=False),
        sa.Column("animal_name", sa.String(length=50), nullable=False),
        sa.Column("breed_name", sa.String(length=100), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_animals_ticket_id", "animals", ["ticket_id"], unique=False)

    op.create_table(
        "audio_files",
        sa.Column("ticket_id", sa.String(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("audio_file_id", sa.String(length=50), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audio_file_id", name="uq_audio_files_audio_file_id"),
        sa.UniqueConstraint("ticket_id", name="uq_audio_files_ticket_id"),
    )
    op.create_index("ix_audio_files_audio_file_id", "audio_files", ["audio_file_id"], unique=False)
    op.create_index("ix_audio_files_client_id", "audio_files", ["client_id"], unique=False)
    op.create_index("ix_audio_files_ticket_id", "audio_files", ["ticket_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audio_files_ticket_id", table_name="audio_files")
    op.drop_index("ix_audio_files_client_id", table_name="audio_files")
    op.drop_index("ix_audio_files_audio_file_id", table_name="audio_files")
    op.drop_table("audio_files")
    op.drop_index("ix_animals_ticket_id", table_name="animals")
    op.drop_table("animals")
    op.drop_index("ix_tickets_ticket_status", table_name="tickets")
    op.drop_index("ix_tickets_ticket_id", table_name="tickets")
    op.drop_index("ix_tickets_client_id", table_name="tickets")
    op.drop_table("tickets")
    op.drop_index("ix_clients_client_id", table_name="clients")
    op.drop_table("clients")
