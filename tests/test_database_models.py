from __future__ import annotations

from sqlalchemy import UniqueConstraint, inspect

from app.db.models import AnimalDB, AudioFileDB, Base, ClientDB, TicketDB


def test_foundation_tables_registered_on_metadata() -> None:
    assert {"clients", "tickets", "animals", "audio_files"}.issubset(Base.metadata.tables)


def test_ticket_foreign_keys_and_unique_business_key() -> None:
    ticket_table = TicketDB.__table__
    foreign_keys = {foreign_key.parent.name: foreign_key.column.table.name for foreign_key in ticket_table.foreign_keys}

    assert foreign_keys["client_id"] == "clients"
    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_tickets_ticket_id"
        and [column.name for column in constraint.columns] == ["ticket_id"]
        for constraint in ticket_table.constraints
    )


def test_child_tables_have_required_foreign_keys() -> None:
    animal_foreign_keys = {
        foreign_key.parent.name: foreign_key.column.table.name
        for foreign_key in AnimalDB.__table__.foreign_keys
    }
    audio_foreign_keys = {
        foreign_key.parent.name: foreign_key.column.table.name
        for foreign_key in AudioFileDB.__table__.foreign_keys
    }

    assert animal_foreign_keys["ticket_id"] == "tickets"
    assert audio_foreign_keys["ticket_id"] == "tickets"
    assert audio_foreign_keys["client_id"] == "clients"


def test_audio_file_has_one_file_per_ticket_constraint() -> None:
    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_audio_files_ticket_id"
        and [column.name for column in constraint.columns] == ["ticket_id"]
        for constraint in AudioFileDB.__table__.constraints
    )


def test_model_relationships_are_configured() -> None:
    ticket_relationships = inspect(TicketDB).relationships
    client_relationships = inspect(ClientDB).relationships

    assert "client" in ticket_relationships
    assert "animals" in ticket_relationships
    assert "audio_file" in ticket_relationships
    assert "tickets" in client_relationships
    assert "audio_files" in client_relationships
