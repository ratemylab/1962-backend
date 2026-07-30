from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.security import verify_token
from app.db.models import ClientDB
from app.db.session import get_db
from app.main import app


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _FakeSession:
    def __init__(self) -> None:
        self.clients_by_client_id: dict[str, ClientDB] = {}
        self._pending: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.commit_error: Exception | None = None

    async def execute(self, statement: object) -> _ScalarResult:
        entity = statement.column_descriptions[0].get("entity")
        params = statement.compile().params
        value = next(iter(params.values()), None)
        if entity is ClientDB:
            return _ScalarResult(self.clients_by_client_id.get(value))
        return _ScalarResult(None)

    def add(self, obj: object) -> None:
        self._pending.append(obj)

    async def commit(self) -> None:
        if self.commit_error is not None:
            raise self.commit_error
        for obj in self._pending:
            if isinstance(obj, ClientDB):
                if obj.id is None:
                    obj.id = str(uuid.uuid4())
                self.clients_by_client_id[obj.client_id] = obj
        self._pending.clear()
        self.commits += 1

    async def rollback(self) -> None:
        self._pending.clear()
        self.rollbacks += 1

    async def refresh(self, obj: object) -> None:
        return None


@pytest.fixture
def fake_db() -> _FakeSession:
    return _FakeSession()


@pytest.fixture
def client(fake_db: _FakeSession) -> Generator[TestClient, None, None]:
    async def override_get_db() -> AsyncGenerator[_FakeSession, None]:
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _payload(client_id: str = "client_up_001") -> dict[str, Any]:
    return {"clientId": client_id, "clientName": "Field App - Uttar Pradesh"}


def test_create_client_success_returns_201(client: TestClient, fake_db: _FakeSession) -> None:
    response = client.post("/api/v1/admin/clients", json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["clientId"] == "client_up_001"
    assert body["clientName"] == "Field App - Uttar Pradesh"
    assert body["apiToken"]
    assert "client_up_001" in fake_db.clients_by_client_id


def test_create_client_returns_api_token_in_response(client: TestClient) -> None:
    response = client.post("/api/v1/admin/clients", json=_payload())

    assert response.status_code == 201
    token = response.json()["apiToken"]
    assert isinstance(token, str)
    # secrets.token_urlsafe(32) produces a sufficiently long opaque string
    assert len(token) >= 32


def test_create_client_stores_hashed_token_not_plaintext(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    response = client.post("/api/v1/admin/clients", json=_payload())

    assert response.status_code == 201
    plaintext_token = response.json()["apiToken"]

    stored = fake_db.clients_by_client_id["client_up_001"]
    # The stored value is a hash, not the plaintext, and it verifies correctly.
    assert stored.hashed_token != plaintext_token
    assert plaintext_token not in stored.hashed_token
    assert stored.hashed_token.startswith("sha256$")
    assert verify_token(plaintext_token, stored.hashed_token)


def test_create_client_duplicate_client_id_returns_409(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    fake_db.clients_by_client_id["client_up_001"] = ClientDB(
        id="existing-id",
        client_id="client_up_001",
        client_name="Existing",
        hashed_token="sha256$deadbeef",
        is_active=True,
    )

    response = client.post("/api/v1/admin/clients", json=_payload())

    assert response.status_code == 409
    # No second row is written for the rejected duplicate.
    assert fake_db.clients_by_client_id["client_up_001"].client_name == "Existing"


def test_create_client_duplicate_via_db_integrity_returns_409(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    # Simulate a race where the row passes the pre-check but the unique
    # constraint rejects the insert; the CRUD layer maps it to 409.
    fake_db.commit_error = IntegrityError("INSERT", {}, Exception("duplicate client_id"))

    response = client.post("/api/v1/admin/clients", json=_payload())

    assert response.status_code == 409
    assert fake_db.rollbacks == 1


def test_create_client_missing_client_id_returns_400(client: TestClient) -> None:
    response = client.post("/api/v1/admin/clients", json={"clientName": "No Id"})

    assert response.status_code == 400


def test_create_client_missing_client_name_returns_400(client: TestClient) -> None:
    response = client.post("/api/v1/admin/clients", json={"clientId": "client_up_002"})

    assert response.status_code == 400


def test_create_client_blank_client_id_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/clients",
        json={"clientId": "", "clientName": "Field App"},
    )

    assert response.status_code == 422


def test_create_client_echoes_x_request_id(client: TestClient) -> None:
    request_id = "7f520de6-46d7-41c9-9978-9b4788335977"
    response = client.post(
        "/api/v1/admin/clients",
        json=_payload(),
        headers={"X-Request-Id": request_id},
    )

    assert response.status_code == 201
    assert response.headers["X-Request-Id"] == request_id


def test_openapi_documents_admin_create_client(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/admin/clients"]["post"]

    assert "201" in operation["responses"]
    for code in ("409", "422", "500"):
        assert code in operation["responses"]

    request_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    request_name = request_ref.split("/")[-1]
    request_schema = schema["components"]["schemas"][request_name]
    assert set(request_schema["properties"]) == {"clientId", "clientName"}

    response_ref = operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
    response_name = response_ref.split("/")[-1]
    response_schema = schema["components"]["schemas"][response_name]
    assert set(response_schema["properties"]) == {"clientId", "clientName", "apiToken"}
