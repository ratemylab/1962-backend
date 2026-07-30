from __future__ import annotations

from sqlalchemy import UniqueConstraint

from app.db.models import ClientDB


def test_client_model_columns() -> None:
    columns = ClientDB.__table__.columns

    assert "id" in columns
    assert "client_id" in columns
    assert "client_name" in columns
    assert "hashed_token" in columns
    assert "is_active" in columns
    assert "created_at" in columns
    assert "updated_at" in columns


def test_client_model_has_unique_public_client_id() -> None:
    unique_constraints = [
        constraint
        for constraint in ClientDB.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert any(
        constraint.name == "uq_clients_client_id"
        and [column.name for column in constraint.columns] == ["client_id"]
        for constraint in unique_constraints
    )


def test_client_model_has_client_id_index() -> None:
    assert any(index.name == "ix_clients_client_id" for index in ClientDB.__table__.indexes)
