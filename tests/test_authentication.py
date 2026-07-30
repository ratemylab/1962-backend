from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.api.deps import (
    EMPTY_AUTH_HEADERS,
    INVALID_CLIENT_CREDENTIALS,
    MISSING_AUTH_HEADERS,
    get_current_client,
)
from app.core.security import hash_token
from app.db.models import ClientDB

# result = await db.execute(query)

# client = result.scalar_one_or_none()
class _ScalarResult:
    def __init__(self, value: ClientDB | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> ClientDB | None:
        return self._value

# await db.execute(...)
# _ScalarResult(self.client)
class _FakeSession:
    def __init__(self, client: ClientDB | None) -> None:
        self.client = client

    async def execute(self, statement: object) -> _ScalarResult:
        return _ScalarResult(self.client)

# Creates a sample client.
def _client(*, token: str = "secret-token", is_active: bool = True) -> ClientDB:
    return ClientDB(
        client_id="client_rj_001",
        client_name="Field App - Rajasthan",
        hashed_token=hash_token(token),
        is_active=is_active,
    )


def test_get_current_client_accepts_valid_credentials() -> None:
    client = _client()

    authenticated = asyncio.run(
        get_current_client(
            db=_FakeSession(client),
            x_client_id="client_rj_001",
            x_api_token="secret-token",
        )
    )

    assert authenticated is client


def test_get_current_client_rejects_both_headers_missing() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_client(
                db=_FakeSession(None),
                x_client_id=None,
                x_api_token=None,
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == MISSING_AUTH_HEADERS


def test_get_current_client_rejects_missing_client_id() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_client(
                db=_FakeSession(_client()),
                x_client_id=None,
                x_api_token="secret-token",
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == MISSING_AUTH_HEADERS


def test_get_current_client_rejects_missing_api_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_client(
                db=_FakeSession(_client()),
                x_client_id="client_rj_001",
                x_api_token=None,
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == MISSING_AUTH_HEADERS


@pytest.mark.parametrize("blank_value", ["", "   ", "\t"])
def test_get_current_client_rejects_empty_client_id(blank_value: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_client(
                db=_FakeSession(_client()),
                x_client_id=blank_value,
                x_api_token="secret-token",
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == EMPTY_AUTH_HEADERS


@pytest.mark.parametrize("blank_value", ["", "   ", "\t"])
def test_get_current_client_rejects_empty_api_token(blank_value: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_client(
                db=_FakeSession(_client()),
                x_client_id="client_rj_001",
                x_api_token=blank_value,
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == EMPTY_AUTH_HEADERS


def test_get_current_client_rejects_unknown_client_id() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_client(
                db=_FakeSession(None),
                x_client_id="client_does_not_exist",
                x_api_token="secret-token",
            )
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == INVALID_CLIENT_CREDENTIALS


def test_get_current_client_rejects_wrong_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_client(
                db=_FakeSession(_client()),
                x_client_id="client_rj_001",
                x_api_token="wrong-token",
            )
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == INVALID_CLIENT_CREDENTIALS


def test_get_current_client_rejects_inactive_client() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_client(
                db=_FakeSession(_client(is_active=False)),
                x_client_id="client_rj_001",
                x_api_token="secret-token",
            )
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == INVALID_CLIENT_CREDENTIALS
