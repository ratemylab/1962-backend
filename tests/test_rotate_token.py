from __future__ import annotations

from collections.abc import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_token, verify_token
from app.db.models import ClientDB
from app.db.session import get_db
from app.main import app
from app.schema.client import TOKEN_ROTATION_MESSAGE

CLIENT_ID = "client_rj_001"
CLIENT_NAME = "Field App - Rajasthan"
ORIGINAL_TOKEN = "original-token"
ROTATE_URL = "/api/v1/admin/clients/rotate-token"


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
    db = _FakeSession()
    db.clients_by_client_id[CLIENT_ID] = ClientDB(
        id="client-internal-id",
        client_id=CLIENT_ID,
        client_name=CLIENT_NAME,
        hashed_token=hash_token(ORIGINAL_TOKEN),
        is_active=True,
    )
    return db


@pytest.fixture
def client(fake_db: _FakeSession) -> Generator[TestClient, None, None]:
    async def override_get_db() -> AsyncGenerator[_FakeSession, None]:
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _auth_headers(token: str = ORIGINAL_TOKEN, client_id: str = CLIENT_ID) -> dict[str, str]:
    return {"X-Client-Id": client_id, "X-Api-Token": token}


def test_rotate_token_success_returns_200(client: TestClient) -> None:
    response = client.post(ROTATE_URL, headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["clientId"] == CLIENT_ID
    assert body["clientName"] == CLIENT_NAME
    assert body["apiToken"]
    assert body["message"] == TOKEN_ROTATION_MESSAGE


def test_rotate_token_response_contains_client_id_and_api_token(client: TestClient) -> None:
    response = client.post(ROTATE_URL, headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"clientId", "clientName", "apiToken", "message"}
    assert isinstance(body["apiToken"], str)
    assert len(body["apiToken"]) >= 32


def test_rotate_token_changes_hashed_token_in_database(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    original_hash = fake_db.clients_by_client_id[CLIENT_ID].hashed_token

    response = client.post(ROTATE_URL, headers=_auth_headers())

    assert response.status_code == 200
    stored = fake_db.clients_by_client_id[CLIENT_ID]
    assert stored.hashed_token != original_hash
    assert verify_token(response.json()["apiToken"], stored.hashed_token)
    assert fake_db.commits == 1


def test_rotate_token_never_exposes_hashed_token(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    response = client.post(ROTATE_URL, headers=_auth_headers())

    assert response.status_code == 200
    assert "hashed_token" not in response.text
    assert "hashedToken" not in response.text
    # The stored hash itself must not leak into the payload.
    assert fake_db.clients_by_client_id[CLIENT_ID].hashed_token not in response.text


def test_rotate_token_does_not_store_plaintext_token(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    response = client.post(ROTATE_URL, headers=_auth_headers())

    new_token = response.json()["apiToken"]
    stored = fake_db.clients_by_client_id[CLIENT_ID]
    assert stored.hashed_token != new_token
    assert new_token not in stored.hashed_token
    assert stored.hashed_token.startswith("sha256$")


def test_new_token_authenticates_successfully(client: TestClient) -> None:
    first = client.post(ROTATE_URL, headers=_auth_headers())
    assert first.status_code == 200
    new_token = first.json()["apiToken"]

    # Reusing the freshly issued token must authenticate on a subsequent call.
    second = client.post(ROTATE_URL, headers=_auth_headers(token=new_token))

    assert second.status_code == 200
    assert second.json()["apiToken"] != new_token


def test_old_token_no_longer_authenticates(client: TestClient) -> None:
    response = client.post(ROTATE_URL, headers=_auth_headers())
    assert response.status_code == 200

    replayed = client.post(ROTATE_URL, headers=_auth_headers(token=ORIGINAL_TOKEN))

    assert replayed.status_code == 401
    assert replayed.json()["message"] == "Invalid client credentials"


def test_rotated_token_authenticates_against_other_endpoints(client: TestClient) -> None:
    new_token = client.post(ROTATE_URL, headers=_auth_headers()).json()["apiToken"]

    # A ticket call with the old token is rejected, while the new token passes
    # authentication (and only then fails body validation).
    stale = client.put("/api/v1/tickets/12345678", json={}, headers=_auth_headers())
    assert stale.status_code == 401

    fresh = client.put(
        "/api/v1/tickets/12345678",
        json={},
        headers=_auth_headers(token=new_token),
    )
    assert fresh.status_code == 400


def test_rotate_token_missing_auth_headers_returns_400(client: TestClient) -> None:
    response = client.post(ROTATE_URL)

    assert response.status_code == 400
    assert response.json()["message"] == "Missing required authentication headers."


def test_rotate_token_invalid_token_returns_401(client: TestClient) -> None:
    response = client.post(ROTATE_URL, headers=_auth_headers(token="wrong-token"))

    assert response.status_code == 401


def test_rotate_token_inactive_client_returns_401(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    fake_db.clients_by_client_id[CLIENT_ID].is_active = False

    response = client.post(ROTATE_URL, headers=_auth_headers())

    assert response.status_code == 401


def test_rotate_token_rolls_back_on_commit_failure(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    fake_db.commit_error = RuntimeError("commit failed")

    with pytest.raises(RuntimeError):
        client.post(ROTATE_URL, headers=_auth_headers())

    assert fake_db.rollbacks == 1
    assert fake_db.commits == 0


def test_openapi_documents_rotate_token(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/admin/clients/rotate-token"]["post"]

    assert operation["summary"] == "Rotate API Token"
    assert "returned only once" in operation["description"]
    assert "requestBody" not in operation

    for code in ("200", "400", "401", "500"):
        assert code in operation["responses"]

    response_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    response_schema = schema["components"]["schemas"][response_ref.split("/")[-1]]
    assert set(response_schema["properties"]) == {
        "clientId",
        "clientName",
        "apiToken",
        "message",
    }
