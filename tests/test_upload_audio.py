from __future__ import annotations

import re
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_token
from app.db.models import AudioFileDB, ClientDB, TicketDB
from app.db.session import get_db
from app.main import app
from app.services.audio_service import AudioService, get_audio_service

TICKET_ID = "12345678"
CLIENT_PK = "client-internal-id"
TICKET_PK = "ticket-internal-id"


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _FakeSession:
    def __init__(self) -> None:
        self.clients_by_client_id: dict[str, ClientDB] = {}
        self.tickets_by_ticket_id: dict[str, TicketDB] = {}
        self.audio_by_ticket_pk: dict[str, AudioFileDB] = {}
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
        if entity is TicketDB:
            return _ScalarResult(self.tickets_by_ticket_id.get(value))
        if entity is AudioFileDB:
            return _ScalarResult(self.audio_by_ticket_pk.get(value))
        return _ScalarResult(None)

    def add(self, obj: object) -> None:
        self._pending.append(obj)

    async def commit(self) -> None:
        if self.commit_error is not None:
            raise self.commit_error
        for obj in self._pending:
            if isinstance(obj, AudioFileDB):
                if obj.id is None:
                    obj.id = str(uuid.uuid4())
                self.audio_by_ticket_pk[obj.ticket_id] = obj
        self._pending.clear()
        self.commits += 1

    async def rollback(self) -> None:
        self._pending.clear()
        self.rollbacks += 1

    async def refresh(self, obj: object) -> None:
        return None


@pytest.fixture
def upload_dir(tmp_path: Path) -> Path:
    return tmp_path / "audio"


@pytest.fixture
def fake_db() -> _FakeSession:
    db = _FakeSession()
    client = ClientDB(
        id=CLIENT_PK,
        client_id="client_rj_001",
        client_name="Field App - Rajasthan",
        hashed_token=hash_token("valid-token"),
        is_active=True,
    )
    db.clients_by_client_id[client.client_id] = client
    db.tickets_by_ticket_id[TICKET_ID] = TicketDB(
        id=TICKET_PK,
        ticket_id=TICKET_ID,
        client_id=CLIENT_PK,
        ticket_status="OPEN",
        type="Complaint",
        created_date_time=datetime.now(timezone.utc),
        farmer_id="F001234",
        farmer_name="Ramesh Kumar",
        village_id=1234,
        village="Seel",
        panchayat_id=9876,
        panchayat="Sinronj",
        block_id=892739,
        block="Arain",
        district="Ajmer",
        state="Rajasthan",
        disease="Lameness",
        symptoms=["Difficulty in walking"],
    )
    return db


@pytest.fixture
def client(fake_db: _FakeSession, upload_dir: Path) -> Generator[TestClient, None, None]:
    async def override_get_db() -> AsyncGenerator[_FakeSession, None]:
        yield fake_db

    service = AudioService(upload_dir=upload_dir)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_audio_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _auth_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"X-Client-Id": "client_rj_001", "X-Api-Token": "valid-token"}
    if extra:
        headers.update(extra)
    return headers


def _audio_file(
    filename: str = f"ticket_{TICKET_ID}.ogg",
    content: bytes = b"fake-audio-bytes",
    content_type: str = "audio/ogg",
) -> dict[str, tuple[str, bytes, str]]:
    return {"audioFile": (filename, content, content_type)}


def test_upload_audio_success_returns_201_and_persists(
    client: TestClient,
    fake_db: _FakeSession,
    upload_dir: Path,
) -> None:
    response = client.post(
        f"/api/v1/tickets/{TICKET_ID}/audio",
        files=_audio_file(),
        headers=_auth_headers(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["ticketId"] == TICKET_ID
    assert body["fileName"] == f"ticket_{TICKET_ID}.ogg"
    assert body["audioFileId"].startswith("af-")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", body["uploadedAt"])

    assert TICKET_PK in fake_db.audio_by_ticket_pk
    persisted = fake_db.audio_by_ticket_pk[TICKET_PK]
    assert persisted.client_id == CLIENT_PK
    assert persisted.file_name == f"ticket_{TICKET_ID}.ogg"

    stored_files = list(upload_dir.iterdir())
    assert len(stored_files) == 1
    assert stored_files[0].read_bytes() == b"fake-audio-bytes"


def test_upload_audio_missing_auth_headers_returns_400(client: TestClient) -> None:
    response = client.post(f"/api/v1/tickets/{TICKET_ID}/audio", files=_audio_file())
    assert response.status_code == 400
    assert response.json()["message"] == "Missing required authentication headers."


def test_upload_audio_empty_auth_header_returns_400(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/tickets/{TICKET_ID}/audio",
        files=_audio_file(),
        headers={"X-Client-Id": "", "X-Api-Token": "valid-token"},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Authentication headers cannot be empty."


def test_upload_audio_invalid_token_returns_401(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/tickets/{TICKET_ID}/audio",
        files=_audio_file(),
        headers={"X-Client-Id": "client_rj_001", "X-Api-Token": "wrong-token"},
    )
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid client credentials"


def test_upload_audio_inactive_client_returns_401(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    fake_db.clients_by_client_id["client_rj_001"].is_active = False

    response = client.post(
        f"/api/v1/tickets/{TICKET_ID}/audio",
        files=_audio_file(),
        headers=_auth_headers(),
    )
    assert response.status_code == 401


def test_upload_audio_unknown_ticket_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tickets/does-not-exist/audio",
        files=_audio_file(filename="ticket_does-not-exist.ogg"),
        headers=_auth_headers(),
    )
    assert response.status_code == 404


def test_upload_audio_wrong_owner_returns_403(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    fake_db.tickets_by_ticket_id[TICKET_ID].client_id = "some-other-client"
    response = client.post(
        f"/api/v1/tickets/{TICKET_ID}/audio",
        files=_audio_file(),
        headers=_auth_headers(),
    )
    assert response.status_code == 403


def test_upload_audio_missing_file_returns_400(client: TestClient) -> None:
    response = client.post(f"/api/v1/tickets/{TICKET_ID}/audio", headers=_auth_headers())
    assert response.status_code == 400


def test_upload_audio_unsupported_extension_returns_415(
    client: TestClient,
    upload_dir: Path,
) -> None:
    response = client.post(
        f"/api/v1/tickets/{TICKET_ID}/audio",
        files=_audio_file(filename=f"ticket_{TICKET_ID}.txt", content_type="text/plain"),
        headers=_auth_headers(),
    )
    assert response.status_code == 415
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []


def test_upload_audio_oversized_returns_413(
    client: TestClient,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.audio_service.MAX_AUDIO_UPLOAD_BYTES", 8)
    response = client.post(
        f"/api/v1/tickets/{TICKET_ID}/audio",
        files=_audio_file(content=b"way-too-many-bytes"),
        headers=_auth_headers(),
    )
    assert response.status_code == 413
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []


def test_upload_audio_filename_without_ticket_id_returns_400(
    client: TestClient,
    upload_dir: Path,
) -> None:
    response = client.post(
        f"/api/v1/tickets/{TICKET_ID}/audio",
        files=_audio_file(filename="recording.ogg"),
        headers=_auth_headers(),
    )
    assert response.status_code == 400
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []


def test_upload_audio_duplicate_returns_409(
    client: TestClient,
    fake_db: _FakeSession,
    upload_dir: Path,
) -> None:
    fake_db.audio_by_ticket_pk[TICKET_PK] = AudioFileDB(
        id="existing-audio-id",
        ticket_id=TICKET_PK,
        client_id=CLIENT_PK,
        audio_file_id="af-existing",
        file_name=f"ticket_{TICKET_ID}.ogg",
        storage_path="uploads/audio/af-existing.ogg",
        uploaded_at=datetime.now(timezone.utc),
    )

    response = client.post(
        f"/api/v1/tickets/{TICKET_ID}/audio",
        files=_audio_file(),
        headers=_auth_headers(),
    )
    assert response.status_code == 409
    # No new file should have been written for the rejected duplicate.
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []


def test_upload_audio_db_integrity_error_returns_409_and_cleans_file(
    client: TestClient,
    fake_db: _FakeSession,
    upload_dir: Path,
) -> None:
    fake_db.commit_error = IntegrityError("INSERT", {}, Exception("duplicate ticket_id"))

    response = client.post(
        f"/api/v1/tickets/{TICKET_ID}/audio",
        files=_audio_file(),
        headers=_auth_headers(),
    )

    assert response.status_code == 409
    assert fake_db.rollbacks == 1
    assert list(upload_dir.iterdir()) == []


def test_upload_audio_db_failure_returns_500_and_removes_file(
    client: TestClient,
    fake_db: _FakeSession,
    upload_dir: Path,
) -> None:
    fake_db.commit_error = RuntimeError("unexpected db failure")

    # An unexpected persistence error surfaces as a 500 via the default server
    # error middleware; disable re-raising so we observe the HTTP response.
    raw_client = TestClient(app, raise_server_exceptions=False)
    response = raw_client.post(
        f"/api/v1/tickets/{TICKET_ID}/audio",
        files=_audio_file(),
        headers=_auth_headers(),
    )

    assert response.status_code == 500
    assert fake_db.rollbacks == 1
    assert list(upload_dir.iterdir()) == []


def test_upload_audio_echoes_x_request_id(client: TestClient) -> None:
    request_id = "7f520de6-46d7-41c9-9978-9b4788335977"
    response = client.post(
        f"/api/v1/tickets/{TICKET_ID}/audio",
        files=_audio_file(),
        headers=_auth_headers({"X-Request-Id": request_id}),
    )

    assert response.status_code == 201
    assert response.headers["X-Request-Id"] == request_id


def test_openapi_documents_multipart_upload(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/tickets/{ticketId}/audio"]["post"]

    content = operation["requestBody"]["content"]
    assert "multipart/form-data" in content

    body_schema = content["multipart/form-data"]["schema"]
    if "$ref" in body_schema:
        ref_name = body_schema["$ref"].split("/")[-1]
        body_schema = schema["components"]["schemas"][ref_name]
    audio_prop = body_schema["properties"]["audioFile"]
    assert audio_prop.get("type") == "string"
    # OpenAPI 3.0 uses format=binary; OpenAPI 3.1 uses contentMediaType.
    assert (
        audio_prop.get("format") == "binary"
        or "contentMediaType" in audio_prop
    )

    assert "201" in operation["responses"]
    for code in ("400", "401", "403", "404", "409", "413", "415", "500"):
        assert code in operation["responses"]


def test_openapi_uploaded_at_documented_as_contract_string(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/tickets/{ticketId}/audio"]["post"]

    response_schema = operation["responses"]["201"]["content"]["application/json"]["schema"]
    ref_name = response_schema["$ref"].split("/")[-1]
    prop = schema["components"]["schemas"][ref_name]["properties"]["uploadedAt"]

    assert prop["type"] == "string"
    assert prop.get("format") != "date-time"
