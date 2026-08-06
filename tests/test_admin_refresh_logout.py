from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    verify_access_token,
    verify_token,
)
from app.db.models import AdminDB, RefreshTokenDB
from app.db.session import get_db
from app.main import app
from app.schema.auth import LOGOUT_MESSAGE

LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
CREATE_CLIENT_URL = "/api/v1/admin/clients"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"
ADMIN_ID = "admin-internal-id"

INVALID_REFRESH_MESSAGE = "Invalid or expired refresh token"


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _FakeSession:
    def __init__(self) -> None:
        self.admins_by_username: dict[str, AdminDB] = {}
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
        id=ADMIN_ID,
        username=ADMIN_USERNAME,
        password_hash=hash_password(ADMIN_PASSWORD),
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


def _login(client: TestClient) -> dict[str, object]:
    response = client.post(
        LOGIN_URL,
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- login issues a refresh token ---------------------------------------------


def test_login_returns_access_and_refresh_token(client: TestClient) -> None:
    body = _login(client)

    assert body["tokenType"] == "Bearer"
    assert verify_access_token(body["accessToken"]) == ADMIN_USERNAME
    assert isinstance(body["refreshToken"], str)
    assert len(body["refreshToken"]) >= 32


def test_login_reports_configured_expiries(client: TestClient) -> None:
    body = _login(client)

    assert body["expiresIn"] == settings.jwt_access_token_expire_minutes * 60
    assert body["refreshExpiresIn"] == settings.refresh_token_expire_days * 86400


def test_login_stores_refresh_token_hashed(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    plaintext = _login(client)["refreshToken"]

    stored = fake_db.refresh_tokens_by_admin_id[ADMIN_ID]
    assert stored.hashed_refresh_token.startswith("sha256$")
    assert verify_token(plaintext, stored.hashed_refresh_token)


def test_login_never_stores_plaintext_refresh_token(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    plaintext = _login(client)["refreshToken"]

    stored = fake_db.refresh_tokens_by_admin_id[ADMIN_ID]
    assert stored.hashed_refresh_token != plaintext
    assert plaintext not in stored.hashed_refresh_token


def test_login_response_never_exposes_hashed_refresh_token(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    response = client.post(
        LOGIN_URL,
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    stored = fake_db.refresh_tokens_by_admin_id[ADMIN_ID]
    assert stored.hashed_refresh_token not in response.text
    assert "hashed_refresh_token" not in response.text
    assert "adminId" not in response.text
    assert ADMIN_ID not in response.text


def test_login_stores_expiry_in_the_future(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    _login(client)

    stored = fake_db.refresh_tokens_by_admin_id[ADMIN_ID]
    expected = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    assert abs((stored.expires_at - expected).total_seconds()) < 60


def test_second_login_keeps_single_refresh_token_row(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    _login(client)
    _login(client)

    assert len(fake_db.refresh_tokens_by_admin_id) == 1


def test_second_login_invalidates_previous_refresh_token(client: TestClient) -> None:
    first = _login(client)["refreshToken"]
    second = _login(client)["refreshToken"]

    assert first != second
    assert client.post(REFRESH_URL, json={"refreshToken": first}).status_code == 401
    assert client.post(REFRESH_URL, json={"refreshToken": second}).status_code == 200


# --- refresh ------------------------------------------------------------------


def test_refresh_with_valid_token_returns_new_access_token(client: TestClient) -> None:
    refresh_token = _login(client)["refreshToken"]

    response = client.post(REFRESH_URL, json={"refreshToken": refresh_token})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"accessToken", "tokenType", "expiresIn"}
    assert body["tokenType"] == "Bearer"
    assert body["expiresIn"] == settings.jwt_access_token_expire_minutes * 60
    assert verify_access_token(body["accessToken"]) == ADMIN_USERNAME


def test_refreshed_access_token_works_on_admin_endpoint(client: TestClient) -> None:
    refresh_token = _login(client)["refreshToken"]
    access_token = client.post(
        REFRESH_URL, json={"refreshToken": refresh_token}
    ).json()["accessToken"]

    response = client.post(
        CREATE_CLIENT_URL,
        json={"clientId": "client_up_001", "clientName": "Field App"},
        headers=_bearer(access_token),
    )

    assert response.status_code == 201


def test_refresh_does_not_rotate_refresh_token(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    refresh_token = _login(client)["refreshToken"]
    stored_before = fake_db.refresh_tokens_by_admin_id[ADMIN_ID].hashed_refresh_token

    response = client.post(REFRESH_URL, json={"refreshToken": refresh_token})

    assert "refreshToken" not in response.json()
    assert fake_db.refresh_tokens_by_admin_id[ADMIN_ID].hashed_refresh_token == stored_before
    # The same refresh token stays usable for the next renewal.
    assert client.post(REFRESH_URL, json={"refreshToken": refresh_token}).status_code == 200


def test_refresh_with_unknown_token_returns_401(client: TestClient) -> None:
    _login(client)

    response = client.post(REFRESH_URL, json={"refreshToken": "not-a-real-token"})

    assert response.status_code == 401
    assert response.json()["message"] == INVALID_REFRESH_MESSAGE


def test_refresh_with_expired_token_returns_401(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    refresh_token = _login(client)["refreshToken"]
    fake_db.refresh_tokens_by_admin_id[ADMIN_ID].expires_at = datetime.now(
        timezone.utc
    ) - timedelta(seconds=1)

    response = client.post(REFRESH_URL, json={"refreshToken": refresh_token})

    assert response.status_code == 401
    assert response.json()["message"] == INVALID_REFRESH_MESSAGE


def test_refresh_with_deleted_token_returns_401(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    refresh_token = _login(client)["refreshToken"]
    fake_db.refresh_tokens_by_admin_id.clear()

    response = client.post(REFRESH_URL, json={"refreshToken": refresh_token})

    assert response.status_code == 401


def test_refresh_with_inactive_admin_returns_401(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    refresh_token = _login(client)["refreshToken"]
    fake_db.admins_by_username[ADMIN_USERNAME].is_active = False

    response = client.post(REFRESH_URL, json={"refreshToken": refresh_token})

    assert response.status_code == 401


def test_refresh_does_not_accept_an_access_token(client: TestClient) -> None:
    access_token = _login(client)["accessToken"]

    response = client.post(REFRESH_URL, json={"refreshToken": access_token})

    assert response.status_code == 401


def test_refresh_requires_no_credentials_header(client: TestClient) -> None:
    refresh_token = _login(client)["refreshToken"]

    # No Authorization header is sent; the refresh token alone is sufficient.
    response = client.post(REFRESH_URL, json={"refreshToken": refresh_token})

    assert response.status_code == 200


def test_refresh_missing_field_returns_400(client: TestClient) -> None:
    assert client.post(REFRESH_URL, json={}).status_code == 400


def test_refresh_blank_token_returns_422(client: TestClient) -> None:
    assert client.post(REFRESH_URL, json={"refreshToken": ""}).status_code == 422


def test_refresh_response_never_exposes_stored_hash(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    refresh_token = _login(client)["refreshToken"]

    response = client.post(REFRESH_URL, json={"refreshToken": refresh_token})

    stored = fake_db.refresh_tokens_by_admin_id[ADMIN_ID]
    assert stored.hashed_refresh_token not in response.text
    assert ADMIN_ID not in response.text


# --- logout -------------------------------------------------------------------


def test_logout_returns_success_message(client: TestClient) -> None:
    access_token = _login(client)["accessToken"]

    response = client.post(LOGOUT_URL, headers=_bearer(access_token))

    assert response.status_code == 200
    assert response.json() == {"message": LOGOUT_MESSAGE}


def test_logout_removes_refresh_token(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    access_token = _login(client)["accessToken"]
    assert ADMIN_ID in fake_db.refresh_tokens_by_admin_id

    client.post(LOGOUT_URL, headers=_bearer(access_token))

    assert fake_db.refresh_tokens_by_admin_id == {}


def test_refresh_after_logout_returns_401(client: TestClient) -> None:
    body = _login(client)

    client.post(LOGOUT_URL, headers=_bearer(body["accessToken"]))

    response = client.post(REFRESH_URL, json={"refreshToken": body["refreshToken"]})
    assert response.status_code == 401
    assert response.json()["message"] == INVALID_REFRESH_MESSAGE


def test_logout_without_token_returns_401(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    _login(client)

    response = client.post(LOGOUT_URL)

    assert response.status_code == 401
    assert ADMIN_ID in fake_db.refresh_tokens_by_admin_id


def test_logout_with_invalid_token_returns_401(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    _login(client)

    response = client.post(LOGOUT_URL, headers=_bearer("not-a-jwt"))

    assert response.status_code == 401
    assert ADMIN_ID in fake_db.refresh_tokens_by_admin_id


def test_logout_with_expired_access_token_returns_401(client: TestClient) -> None:
    _login(client)
    expired = create_access_token(ADMIN_USERNAME, expires_delta=timedelta(minutes=-1))

    assert client.post(LOGOUT_URL, headers=_bearer(expired)).status_code == 401


def test_logout_is_idempotent(client: TestClient) -> None:
    access_token = _login(client)["accessToken"]

    assert client.post(LOGOUT_URL, headers=_bearer(access_token)).status_code == 200
    # The access token itself stays valid until expiry, so a repeat call succeeds.
    assert client.post(LOGOUT_URL, headers=_bearer(access_token)).status_code == 200


def test_login_after_logout_issues_a_working_refresh_token(client: TestClient) -> None:
    first = _login(client)
    client.post(LOGOUT_URL, headers=_bearer(first["accessToken"]))

    second = _login(client)

    assert client.post(
        REFRESH_URL, json={"refreshToken": second["refreshToken"]}
    ).status_code == 200


def test_admin_endpoint_still_requires_valid_access_token_after_logout(
    client: TestClient,
) -> None:
    access_token = _login(client)["accessToken"]
    client.post(LOGOUT_URL, headers=_bearer(access_token))

    payload = {"clientId": "client_up_002", "clientName": "Field App"}
    assert client.post(CREATE_CLIENT_URL, json=payload).status_code == 401
    assert client.post(
        CREATE_CLIENT_URL, json=payload, headers=_bearer("not-a-jwt")
    ).status_code == 401


# --- security -----------------------------------------------------------------


def test_stored_hash_matches_hash_token_helper(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    plaintext = _login(client)["refreshToken"]

    stored = fake_db.refresh_tokens_by_admin_id[ADMIN_ID]
    assert stored.hashed_refresh_token == hash_token(plaintext)


def test_refresh_token_is_not_a_jwt(client: TestClient) -> None:
    refresh_token = _login(client)["refreshToken"]

    # Opaque random string, so it carries no claims and cannot be self-validated.
    assert refresh_token.count(".") != 2
    assert verify_access_token(refresh_token) is None


def test_each_login_generates_a_distinct_refresh_token(client: TestClient) -> None:
    tokens = {_login(client)["refreshToken"] for _ in range(3)}

    assert len(tokens) == 3


# --- OpenAPI ------------------------------------------------------------------


def test_openapi_documents_refresh(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][REFRESH_URL]["post"]

    assert operation["summary"] == "Refresh admin access token"
    # Refresh is reached without an access token, so it carries no security.
    assert "security" not in operation
    for code in ("200", "400", "401", "422", "500"):
        assert code in operation["responses"]

    request_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    request_schema = schema["components"]["schemas"][request_ref.split("/")[-1]]
    assert set(request_schema["properties"]) == {"refreshToken"}

    response_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    response_schema = schema["components"]["schemas"][response_ref.split("/")[-1]]
    assert set(response_schema["properties"]) == {"accessToken", "tokenType", "expiresIn"}


def test_openapi_documents_logout(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][LOGOUT_URL]["post"]

    assert operation["summary"] == "Admin logout"
    assert operation["security"] == [{"AdminBearerAuth": []}]
    for code in ("200", "401", "500"):
        assert code in operation["responses"]

    response_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    response_schema = schema["components"]["schemas"][response_ref.split("/")[-1]]
    assert set(response_schema["properties"]) == {"message"}


def test_openapi_never_documents_hashed_refresh_token(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    for name, definition in schema["components"]["schemas"].items():
        if name.startswith(("AdminLogin", "RefreshToken", "Logout")):
            assert "hashedRefreshToken" not in definition.get("properties", {})
            assert "hashed_refresh_token" not in definition.get("properties", {})
