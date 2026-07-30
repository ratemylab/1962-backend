from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_token
from app.db.models import ClientDB, TicketDB
from app.db.services.crud_ticket import ticket_crud
from app.db.session import get_db
from app.main import app
from app.schema.ticket import TicketUpdateRequest


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _FakeSession:
    def __init__(self) -> None:
        self.clients_by_client_id: dict[str, ClientDB] = {}
        self.tickets_by_ticket_id: dict[str, TicketDB] = {}
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
        return _ScalarResult(None)

    def add(self, obj: object) -> None:
        self._pending.append(obj)

    async def commit(self) -> None:
        if self.commit_error is not None:
            raise self.commit_error
        for obj in self._pending:
            if isinstance(obj, TicketDB):
                if obj.id is None:
                    obj.id = str(uuid.uuid4())
                self.tickets_by_ticket_id[obj.ticket_id] = obj
        self._pending.clear()
        self.commits += 1

    async def rollback(self) -> None:
        self._pending.clear()
        self.rollbacks += 1

    async def refresh(self, obj: object) -> None:
        return None


def _seed_ticket(*, client_id: str = "client-internal-id", ticket_id: str = "12345678") -> TicketDB:
    return TicketDB(
        id="ticket-internal-id",
        ticket_id=ticket_id,
        client_id=client_id,
        ticket_status="OPEN",
        type="Complaint",
        created_date_time=datetime.now(timezone.utc) - timedelta(hours=1),
        closed_date_time=None,
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
        treatment_given=None,
    )


@pytest.fixture
def fake_db() -> _FakeSession:
    db = _FakeSession()
    client = ClientDB(
        id="client-internal-id",
        client_id="client_rj_001",
        client_name="Field App - Rajasthan",
        hashed_token=hash_token("valid-token"),
        is_active=True,
    )
    db.clients_by_client_id[client.client_id] = client
    ticket = _seed_ticket()
    db.tickets_by_ticket_id[ticket.ticket_id] = ticket
    return db


@pytest.fixture
def client(fake_db: _FakeSession) -> Generator[TestClient, None, None]:
    async def override_get_db() -> AsyncGenerator[_FakeSession, None]:
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _closed_payload(ticket_id: str = "12345678") -> dict[str, Any]:
    closed_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    return {
        "ticketId": ticket_id,
        "ticketDetails": {
            "ticketStatus": "CLOSED",
            "closedDateTime": closed_at.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "mvuDetails": {
            "doctorId": "DR001",
            "doctorName": "Dr. XYZ",
            "paravetId": "PV001",
            "paravetName": "John",
            "mvuNumber": "MVU001",
        },
        "diseaseTreatmentDetails": {
            "disease": "Lameness",
            "symptoms": ["Difficulty in walking", "Swelling in leg"],
            "treatmentGiven": "Medication administered",
        },
    }


def _open_payload(ticket_id: str = "12345678") -> dict[str, Any]:
    return {
        "ticketId": ticket_id,
        "ticketDetails": {
            "ticketStatus": "OPEN",
        },
        "mvuDetails": {
            "doctorId": "DR001",
            "doctorName": "Dr. XYZ",
            "paravetId": "PV001",
            "paravetName": "John",
            "mvuNumber": "MVU001",
        },
        "diseaseTreatmentDetails": {
            "disease": "Lameness",
        },
    }


def _auth_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"X-Client-Id": "client_rj_001", "X-Api-Token": "valid-token"}
    if extra:
        headers.update(extra)
    return headers


def test_update_ticket_success_returns_200(client: TestClient, fake_db: _FakeSession) -> None:
    response = client.put("/api/v1/tickets/12345678", json=_closed_payload(), headers=_auth_headers())

    assert response.status_code == 200
    assert response.json() == {"ticketId": "12345678"}


def test_update_ticket_persists_updated_fields(client: TestClient, fake_db: _FakeSession) -> None:
    response = client.put("/api/v1/tickets/12345678", json=_closed_payload(), headers=_auth_headers())

    assert response.status_code == 200
    ticket = fake_db.tickets_by_ticket_id["12345678"]
    assert ticket.ticket_status == "CLOSED"
    assert ticket.closed_date_time is not None
    assert ticket.doctor_id == "DR001"
    assert ticket.doctor_name == "Dr. XYZ"
    assert ticket.paravet_id == "PV001"
    assert ticket.paravet_name == "John"
    assert ticket.mvu_number == "MVU001"
    assert ticket.treatment_given == "Medication administered"
    assert ticket.symptoms == ["Difficulty in walking", "Swelling in leg"]
    # Create-only data is untouched
    assert ticket.farmer_id == "F001234"
    assert ticket.village == "Seel"


def test_update_ticket_missing_auth_headers_returns_400(client: TestClient) -> None:
    response = client.put("/api/v1/tickets/12345678", json=_closed_payload())

    assert response.status_code == 400
    assert response.json()["message"] == "Missing required authentication headers."


def test_update_ticket_empty_auth_header_returns_400(client: TestClient) -> None:
    response = client.put(
        "/api/v1/tickets/12345678",
        json=_closed_payload(),
        headers={"X-Client-Id": "client_rj_001", "X-Api-Token": "  "},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Authentication headers cannot be empty."


def test_update_ticket_invalid_token_returns_401(client: TestClient) -> None:
    response = client.put(
        "/api/v1/tickets/12345678",
        json=_closed_payload(),
        headers={"X-Client-Id": "client_rj_001", "X-Api-Token": "wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid client credentials"


def test_update_ticket_inactive_client_returns_401(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    fake_db.clients_by_client_id["client_rj_001"].is_active = False

    response = client.put("/api/v1/tickets/12345678", json=_closed_payload(), headers=_auth_headers())

    assert response.status_code == 401


def test_update_ticket_unknown_ticket_returns_404(client: TestClient) -> None:
    response = client.put(
        "/api/v1/tickets/99999999",
        json=_closed_payload(ticket_id="99999999"),
        headers=_auth_headers(),
    )

    assert response.status_code == 404


def test_update_ticket_wrong_owner_returns_403(client: TestClient, fake_db: _FakeSession) -> None:
    fake_db.tickets_by_ticket_id["12345678"] = _seed_ticket(client_id="other-client-internal-id")

    response = client.put("/api/v1/tickets/12345678", json=_closed_payload(), headers=_auth_headers())

    assert response.status_code == 403


def test_update_ticket_path_body_mismatch_returns_400(client: TestClient) -> None:
    response = client.put(
        "/api/v1/tickets/12345678",
        json=_closed_payload(ticket_id="87654321"),
        headers=_auth_headers(),
    )

    assert response.status_code == 400


def test_update_ticket_closed_without_closed_datetime_returns_422(client: TestClient) -> None:
    payload = _closed_payload()
    payload["ticketDetails"].pop("closedDateTime")

    response = client.put("/api/v1/tickets/12345678", json=payload, headers=_auth_headers())

    assert response.status_code == 422


def test_update_ticket_open_with_unexpected_closed_datetime_returns_422(client: TestClient) -> None:
    payload = _open_payload()
    closed_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    payload["ticketDetails"]["closedDateTime"] = closed_at.strftime("%Y-%m-%d %H:%M:%S")

    response = client.put("/api/v1/tickets/12345678", json=payload, headers=_auth_headers())

    assert response.status_code == 422


def test_update_ticket_open_status_succeeds(client: TestClient, fake_db: _FakeSession) -> None:
    response = client.put("/api/v1/tickets/12345678", json=_open_payload(), headers=_auth_headers())

    assert response.status_code == 200
    assert fake_db.tickets_by_ticket_id["12345678"].closed_date_time is None


def test_update_ticket_invalid_doctor_name_returns_422(client: TestClient) -> None:
    payload = _closed_payload()
    payload["mvuDetails"]["doctorName"] = "Dr XYZ 123"

    response = client.put("/api/v1/tickets/12345678", json=payload, headers=_auth_headers())

    assert response.status_code == 422


def test_update_ticket_invalid_paravet_name_returns_422(client: TestClient) -> None:
    payload = _closed_payload()
    payload["mvuDetails"]["paravetName"] = "John99"

    response = client.put("/api/v1/tickets/12345678", json=payload, headers=_auth_headers())

    assert response.status_code == 422


def test_update_ticket_invalid_symptoms_returns_422(client: TestClient) -> None:
    payload = _closed_payload()
    payload["diseaseTreatmentDetails"]["symptoms"] = ["x" * 201]

    response = client.put("/api/v1/tickets/12345678", json=payload, headers=_auth_headers())

    assert response.status_code == 422


def test_update_ticket_malformed_datetime_returns_400(client: TestClient) -> None:
    payload = _closed_payload()
    payload["ticketDetails"]["closedDateTime"] = "2026-04-30T09:21:51Z"

    response = client.put("/api/v1/tickets/12345678", json=payload, headers=_auth_headers())

    assert response.status_code == 400


@pytest.mark.parametrize(
    "bad_value",
    [
        "2026-07-22T08:25:53.870Z",
        "2026-07-22T08:25:53",
        "2026-07-22 08:25:53.870",
    ],
)
def test_update_ticket_rejects_non_contract_datetime_formats(
    client: TestClient,
    bad_value: str,
) -> None:
    payload = _closed_payload()
    payload["ticketDetails"]["closedDateTime"] = bad_value

    response = client.put("/api/v1/tickets/12345678", json=payload, headers=_auth_headers())

    assert response.status_code == 400


def test_openapi_closed_date_time_documented_as_contract_string(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    prop = schema["components"]["schemas"]["TicketUpdateDetails"]["properties"]["closedDateTime"]

    # Optional field renders as anyOf[string, null]; the string branch must carry
    # the contract pattern and must not be an ISO-8601 date-time.
    branches = prop.get("anyOf", [prop])
    string_branches = [b for b in branches if b.get("type") == "string"]
    assert string_branches, prop
    assert all(b.get("format") != "date-time" for b in string_branches)
    assert any(
        b.get("pattern") == r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$" for b in string_branches
    )


def test_update_ticket_missing_mandatory_field_returns_400(client: TestClient) -> None:
    payload = _closed_payload()
    payload.pop("mvuDetails")

    response = client.put("/api/v1/tickets/12345678", json=payload, headers=_auth_headers())

    assert response.status_code == 400


def test_update_ticket_future_closed_datetime_accepted(client: TestClient, fake_db: _FakeSession) -> None:
    # The contract does not prohibit a future closedDateTime, so it is accepted.
    payload = _closed_payload()
    future = datetime.now(timezone.utc) + timedelta(days=1)
    payload["ticketDetails"]["closedDateTime"] = future.strftime("%Y-%m-%d %H:%M:%S")

    response = client.put("/api/v1/tickets/12345678", json=payload, headers=_auth_headers())

    assert response.status_code == 200


def test_update_ticket_echoes_x_request_id(client: TestClient) -> None:
    response = client.put(
        "/api/v1/tickets/12345678",
        json=_closed_payload(),
        headers=_auth_headers({"X-Request-Id": "7f520de6-46d7-41c9-9978-9b4788335977"}),
    )

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "7f520de6-46d7-41c9-9978-9b4788335977"


def test_update_ticket_rolls_back_on_failure(fake_db: _FakeSession) -> None:
    fake_db.commit_error = RuntimeError("update failed")
    ticket = fake_db.tickets_by_ticket_id["12345678"]
    request = TicketUpdateRequest.model_validate(_closed_payload())

    with pytest.raises(RuntimeError):
        asyncio.run(ticket_crud.update_ticket(fake_db, ticket=ticket, obj_in=request))

    assert fake_db.rollbacks == 1
    assert fake_db.commits == 0
