from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    verify_access_token,
    verify_password,
)
from app.db.models import AdminDB, ClientDB, RefreshTokenDB
from app.db.session import get_db
from app.main import app

LOGIN_URL = "/api/v1/auth/login"
CREATE_CLIENT_URL = "/api/v1/admin/clients"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"

CLIENT_ID = "client_rj_001"
CLIENT_TOKEN = "valid-token"


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _FakeSession:
    def __init__(self) -> None:
        self.admins_by_username: dict[str, AdminDB] = {}
        self.clients_by_client_id: dict[str, ClientDB] = {}
        self.refresh_tokens_by_admin_id: dict[str, RefreshTokenDB] = {}
        self._pending: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement: object) -> _ScalarResult:
        entity = statement.column_descriptions[0].get("entity")
        params = statement.compile().params
        if entity is AdminDB:
            if "username_1" in params:
                return _ScalarResult(self.admins_by_username.get(params["username_1"]))
            return _ScalarResult(
                next(
                    (
                        admin
                        for admin in self.admins_by_username.values()
                        if admin.id == params.get("id_1")
                    ),
                    None,
                )
            )
        if entity is RefreshTokenDB:
            if "admin_id_1" in params:
                return _ScalarResult(
                    self.refresh_tokens_by_admin_id.get(params["admin_id_1"])
                )
            hashed = params.get("hashed_refresh_token_1")
            return _ScalarResult(
                next(
                    (
                        row
                        for row in self.refresh_tokens_by_admin_id.values()
                        if row.hashed_refresh_token == hashed
                    ),
                    None,
                )
            )
        if entity is ClientDB:
            return _ScalarResult(self.clients_by_client_id.get(params.get("client_id_1")))
        return _ScalarResult(None)

    def add(self, obj: object) -> None:
        self._pending.append(obj)

    async def delete(self, obj: object) -> None:
        if isinstance(obj, RefreshTokenDB):
            self.refresh_tokens_by_admin_id.pop(obj.admin_id, None)

    async def commit(self) -> None:
        for obj in self._pending:
            if isinstance(obj, RefreshTokenDB):
                self.refresh_tokens_by_admin_id[obj.admin_id] = obj
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
    db.admins_by_username[ADMIN_USERNAME] = AdminDB(
        id="admin-internal-id",
        username=ADMIN_USERNAME,
        password_hash=hash_password(ADMIN_PASSWORD),
        is_active=True,
    )
    db.clients_by_client_id[CLIENT_ID] = ClientDB(
        id="client-internal-id",
        client_id=CLIENT_ID,
        client_name="Field App - Rajasthan",
        hashed_token=hash_token(CLIENT_TOKEN),
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


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _client_payload() -> dict[str, str]:
    return {"clientId": "client_up_001", "clientName": "Field App - Uttar Pradesh"}


# --- password hashing ---------------------------------------------------------


def test_hash_password_never_returns_plaintext() -> None:
    hashed = hash_password(ADMIN_PASSWORD)

    assert hashed != ADMIN_PASSWORD
    assert ADMIN_PASSWORD not in hashed
    assert hashed.startswith("$2b$")


def test_verify_password_accepts_correct_and_rejects_wrong() -> None:
    hashed = hash_password(ADMIN_PASSWORD)

    assert verify_password(ADMIN_PASSWORD, hashed) is True
    assert verify_password("WrongPassword1!", hashed) is False


def test_verify_password_rejects_malformed_hash() -> None:
    assert verify_password(ADMIN_PASSWORD, "not-a-bcrypt-hash") is False


def test_hash_password_is_salted() -> None:
    assert hash_password(ADMIN_PASSWORD) != hash_password(ADMIN_PASSWORD)


# --- token helpers ------------------------------------------------------------


def test_access_token_contains_sub_iat_and_exp() -> None:
    token = create_access_token(ADMIN_USERNAME)

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["sub"] == ADMIN_USERNAME
    assert payload["exp"] > payload["iat"]


def test_verify_access_token_returns_subject() -> None:
    assert verify_access_token(create_access_token(ADMIN_USERNAME)) == ADMIN_USERNAME


def test_verify_access_token_rejects_expired_token() -> None:
    expired = create_access_token(ADMIN_USERNAME, expires_delta=timedelta(minutes=-1))

    assert verify_access_token(expired) is None


def test_verify_access_token_rejects_wrong_signature() -> None:
    forged = jwt.encode({"sub": ADMIN_USERNAME}, "another-secret", algorithm="HS256")

    assert verify_access_token(forged) is None


def test_verify_access_token_rejects_malformed_token() -> None:
    assert verify_access_token("not-a-jwt") is None


# --- login endpoint -----------------------------------------------------------


def test_login_with_valid_credentials_returns_token(client: TestClient) -> None:
    response = client.post(
        LOGIN_URL,
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "accessToken",
        "refreshToken",
        "tokenType",
        "expiresIn",
        "refreshExpiresIn",
    }
    assert body["tokenType"] == "Bearer"
    assert verify_access_token(body["accessToken"]) == ADMIN_USERNAME


def test_login_with_wrong_password_returns_401(client: TestClient) -> None:
    response = client.post(
        LOGIN_URL,
        json={"username": ADMIN_USERNAME, "password": "WrongPassword1!"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid admin credentials"


def test_login_with_unknown_username_returns_401(client: TestClient) -> None:
    response = client.post(
        LOGIN_URL,
        json={"username": "ghost", "password": ADMIN_PASSWORD},
    )

    # Identical to the wrong-password response so usernames cannot be probed.
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid admin credentials"


def test_login_with_inactive_admin_returns_401(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    fake_db.admins_by_username[ADMIN_USERNAME].is_active = False

    response = client.post(
        LOGIN_URL,
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 401


def test_login_never_exposes_password_hash(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    response = client.post(
        LOGIN_URL,
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    assert fake_db.admins_by_username[ADMIN_USERNAME].password_hash not in response.text
    assert "password" not in response.text


def test_login_missing_password_returns_400(client: TestClient) -> None:
    response = client.post(LOGIN_URL, json={"username": ADMIN_USERNAME})

    assert response.status_code == 400


def test_login_blank_username_returns_422(client: TestClient) -> None:
    response = client.post(LOGIN_URL, json={"username": "", "password": ADMIN_PASSWORD})

    assert response.status_code == 422


# --- admin endpoint protection ------------------------------------------------


def test_admin_api_with_valid_jwt_succeeds(client: TestClient) -> None:
    token = client.post(
        LOGIN_URL,
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    ).json()["accessToken"]

    response = client.post(CREATE_CLIENT_URL, json=_client_payload(), headers=_bearer(token))

    assert response.status_code == 201


def test_admin_api_without_authorization_header_returns_401(client: TestClient) -> None:
    response = client.post(CREATE_CLIENT_URL, json=_client_payload())

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_admin_api_with_invalid_jwt_returns_401(client: TestClient) -> None:
    response = client.post(
        CREATE_CLIENT_URL,
        json=_client_payload(),
        headers=_bearer("not-a-jwt"),
    )

    assert response.status_code == 401


def test_admin_api_with_expired_jwt_returns_401(client: TestClient) -> None:
    expired = create_access_token(ADMIN_USERNAME, expires_delta=timedelta(minutes=-1))

    response = client.post(CREATE_CLIENT_URL, json=_client_payload(), headers=_bearer(expired))

    assert response.status_code == 401


def test_admin_api_with_foreign_signature_returns_401(client: TestClient) -> None:
    forged = jwt.encode({"sub": ADMIN_USERNAME}, "another-secret", algorithm="HS256")

    response = client.post(CREATE_CLIENT_URL, json=_client_payload(), headers=_bearer(forged))

    assert response.status_code == 401


def test_admin_api_with_unknown_admin_subject_returns_401(client: TestClient) -> None:
    response = client.post(
        CREATE_CLIENT_URL,
        json=_client_payload(),
        headers=_bearer(create_access_token("ghost")),
    )

    assert response.status_code == 401


def test_admin_api_with_deactivated_admin_returns_401(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    token = create_access_token(ADMIN_USERNAME)
    fake_db.admins_by_username[ADMIN_USERNAME].is_active = False

    response = client.post(CREATE_CLIENT_URL, json=_client_payload(), headers=_bearer(token))

    # A still-unexpired token stops working as soon as the account is disabled.
    assert response.status_code == 401


def test_admin_api_rejects_non_bearer_scheme(client: TestClient) -> None:
    response = client.post(
        CREATE_CLIENT_URL,
        json=_client_payload(),
        headers={"Authorization": f"Basic {create_access_token(ADMIN_USERNAME)}"},
    )

    assert response.status_code == 401


# --- client APIs stay on API-key authentication --------------------------------


def test_client_api_still_accepts_api_key_headers(client: TestClient) -> None:
    response = client.put(
        "/api/v1/tickets/12345678",
        json={},
        headers={"X-Client-Id": CLIENT_ID, "X-Api-Token": CLIENT_TOKEN},
    )

    # Authentication passes; the empty body then fails contract validation.
    assert response.status_code == 400


def test_client_api_rejects_wrong_api_key(client: TestClient) -> None:
    response = client.put(
        "/api/v1/tickets/12345678",
        json={},
        headers={"X-Client-Id": CLIENT_ID, "X-Api-Token": "wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid client credentials"


def test_client_api_does_not_accept_admin_jwt(client: TestClient) -> None:
    response = client.put(
        "/api/v1/tickets/12345678",
        json={},
        headers=_bearer(create_access_token(ADMIN_USERNAME)),
    )

    # Client endpoints still require X-Client-Id / X-Api-Token.
    assert response.status_code == 400
    assert response.json()["message"] == "Missing required authentication headers."


# --- OpenAPI ------------------------------------------------------------------


def test_openapi_documents_login(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][LOGIN_URL]["post"]

    assert operation["summary"] == "Admin login"
    assert "security" not in operation

    for code in ("200", "400", "401", "422", "500"):
        assert code in operation["responses"]

    request_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    request_schema = schema["components"]["schemas"][request_ref.split("/")[-1]]
    assert set(request_schema["properties"]) == {"username", "password"}

    response_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    response_schema = schema["components"]["schemas"][response_ref.split("/")[-1]]
    assert set(response_schema["properties"]) == {
        "accessToken",
        "refreshToken",
        "tokenType",
        "expiresIn",
        "refreshExpiresIn",
    }


def test_openapi_declares_bearer_security_scheme(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    scheme = schema["components"]["securitySchemes"]["AdminBearerAuth"]

    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"


def test_openapi_client_endpoints_keep_header_authentication(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    for path, method in (
        ("/api/v1/tickets", "post"),
        ("/api/v1/tickets/{ticketId}", "put"),
        ("/api/v1/tickets/{ticketId}/audio", "post"),
    ):
        operation = schema["paths"][path][method]
        assert "security" not in operation
        header_params = {
            parameter["name"]
            for parameter in operation.get("parameters", [])
            if parameter["in"] == "header"
        }
        assert {"X-Client-Id", "X-Api-Token"}.issubset(header_params)
