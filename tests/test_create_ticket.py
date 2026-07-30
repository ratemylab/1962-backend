from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_token
from app.db.models import AnimalDB, ClientDB, TicketDB
from app.db.services.crud_ticket import DuplicateTicketError, ticket_crud
from app.db.session import get_db
from app.main import app
from app.schema.ticket import TicketCreateRequest


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _FakeSession:
    def __init__(self) -> None:
        self.clients_by_client_id: dict[str, ClientDB] = {}
        self.tickets_by_ticket_id: dict[str, TicketDB] = {}
        self.animals: list[AnimalDB] = []
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
            # Simulate a persistence failure (e.g. an animal insert failing)
            # before any row is committed, so nothing is persisted.
            raise self.commit_error
        for obj in self._pending:
            if isinstance(obj, TicketDB):
                if obj.id is None:
                    obj.id = str(uuid.uuid4())
                for animal in obj.animals:
                    if animal.id is None:
                        animal.id = str(uuid.uuid4())
                    animal.ticket_id = obj.id
                    self.animals.append(animal)
                self.tickets_by_ticket_id[obj.ticket_id] = obj
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
    client = ClientDB(
        id="client-internal-id",
        client_id="client_rj_001",
        client_name="Field App - Rajasthan",
        hashed_token=hash_token("valid-token"),
        is_active=True,
    )
    db.clients_by_client_id[client.client_id] = client
    return db


@pytest.fixture
def client(fake_db: _FakeSession) -> Generator[TestClient, None, None]:
    async def override_get_db() -> AsyncGenerator[_FakeSession, None]:
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _valid_payload(ticket_id: str = "12345678") -> dict[str, Any]:
    created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    return {
        "ticketId": ticket_id,
        "ticketDetails": {
            "ticketStatus": "OPEN",
            "type": "Complaint",
            "createdDateTime": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "farmerDetails": {
            "farmerId": "F001234",
            "farmerName": "Ramesh Kumar",
        },
        "locationDetails": {
            "villageId": 1234,
            "village": "Seel",
            "panchayatId": 9876,
            "panchayat": "Sinronj",
            "blockId": 892739,
            "block": "Arain",
            "district": "Ajmer",
            "state": "Rajasthan",
            "latitude": 26.414468,
            "longitude": 75.063852,
        },
        "animals": [
            {"animalName": "Cow", "breedName": "HF"},
            {"animalName": "Buffalo", "breedName": "Murrah"},
        ],
        "diseaseTreatmentDetails": {
            "disease": "Lameness",
            "symptoms": [
                "Difficulty in walking",
                "Swelling in leg",
                "Loss of appetite",
            ],
        },
    }


def _auth_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "X-Client-Id": "client_rj_001",
        "X-Api-Token": "valid-token",
    }
    if extra:
        headers.update(extra)
    return headers


def test_create_ticket_valid_request_persists_ticket_and_animals(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    response = client.post("/api/v1/tickets", json=_valid_payload(), headers=_auth_headers())

    assert response.status_code == 201
    assert response.json() == {"ticketId": "12345678"}
    ticket = fake_db.tickets_by_ticket_id["12345678"]
    assert ticket.client_id == "client-internal-id"
    assert ticket.farmer_id == "F001234"
    assert ticket.symptoms == ["Difficulty in walking", "Swelling in leg", "Loss of appetite"]
    assert len(fake_db.animals) == 2


def test_create_ticket_missing_auth_headers_returns_400(client: TestClient) -> None:
    response = client.post("/api/v1/tickets", json=_valid_payload())

    assert response.status_code == 400
    assert response.json()["message"] == "Missing required authentication headers."


def test_create_ticket_missing_client_id_header_returns_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tickets",
        json=_valid_payload(),
        headers={"X-Api-Token": "valid-token"},
    )

    assert response.status_code == 400


def test_create_ticket_missing_api_token_header_returns_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tickets",
        json=_valid_payload(),
        headers={"X-Client-Id": "client_rj_001"},
    )

    assert response.status_code == 400


def test_create_ticket_empty_auth_headers_return_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tickets",
        json=_valid_payload(),
        headers={"X-Client-Id": "   ", "X-Api-Token": "valid-token"},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Authentication headers cannot be empty."

    response = client.post(
        "/api/v1/tickets",
        json=_valid_payload(),
        headers={"X-Client-Id": "client_rj_001", "X-Api-Token": "   "},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Authentication headers cannot be empty."


def test_create_ticket_wrong_auth_returns_401(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tickets",
        json=_valid_payload(),
        headers={"X-Client-Id": "client_rj_001", "X-Api-Token": "wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid client credentials"


def test_create_ticket_unknown_client_id_returns_401(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tickets",
        json=_valid_payload(),
        headers={"X-Client-Id": "client_does_not_exist", "X-Api-Token": "valid-token"},
    )

    assert response.status_code == 401


def test_create_ticket_inactive_client_returns_401(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    fake_db.clients_by_client_id["client_rj_001"].is_active = False

    response = client.post("/api/v1/tickets", json=_valid_payload(), headers=_auth_headers())

    assert response.status_code == 401


def test_create_ticket_duplicate_ticket_id_returns_409(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    fake_db.tickets_by_ticket_id["12345678"] = TicketDB(
        id="existing-ticket-id",
        ticket_id="12345678",
        client_id="client-internal-id",
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

    response = client.post("/api/v1/tickets", json=_valid_payload(), headers=_auth_headers())

    assert response.status_code == 409


def test_create_ticket_missing_mandatory_field_returns_400(client: TestClient) -> None:
    payload = _valid_payload()
    payload.pop("ticketDetails")

    response = client.post("/api/v1/tickets", json=payload, headers=_auth_headers())

    assert response.status_code == 400


def test_create_ticket_invalid_datetime_returns_400(client: TestClient) -> None:
    payload = _valid_payload()
    payload["ticketDetails"]["createdDateTime"] = "2026-04-30T09:21:51Z"

    response = client.post("/api/v1/tickets", json=payload, headers=_auth_headers())

    assert response.status_code == 400


@pytest.mark.parametrize(
    "bad_value",
    [
        "2026-07-22T08:25:53.870Z",  # ISO-8601 with millis + Z
        "2026-07-22T08:25:53",  # ISO-8601 'T' separator
        "2026-07-22 08:25:53.870",  # fractional seconds
        "22-07-2026 08:25:53",  # wrong field order
    ],
)
def test_create_ticket_rejects_non_contract_datetime_formats(
    client: TestClient,
    bad_value: str,
) -> None:
    payload = _valid_payload()
    payload["ticketDetails"]["createdDateTime"] = bad_value

    response = client.post("/api/v1/tickets", json=payload, headers=_auth_headers())

    assert response.status_code == 400


def test_openapi_created_date_time_documented_as_contract_string(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    prop = schema["components"]["schemas"]["TicketDetailsCreate"]["properties"]["createdDateTime"]

    assert prop["type"] == "string"
    assert prop.get("format") != "date-time"
    assert prop["pattern"] == r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"


def test_create_ticket_invalid_coordinates_return_422(client: TestClient) -> None:
    payload = _valid_payload()
    payload["locationDetails"]["latitude"] = 91

    response = client.post("/api/v1/tickets", json=payload, headers=_auth_headers())

    assert response.status_code == 422


def test_create_ticket_animals_validation_returns_422(client: TestClient) -> None:
    payload = _valid_payload()
    payload["animals"] = []

    response = client.post("/api/v1/tickets", json=payload, headers=_auth_headers())

    assert response.status_code == 422


def test_create_ticket_uses_authenticated_client_for_ownership(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    payload = _valid_payload()
    payload["client_id"] = "malicious-client-id"

    response = client.post("/api/v1/tickets", json=payload, headers=_auth_headers())

    assert response.status_code == 422
    assert "12345678" not in fake_db.tickets_by_ticket_id


def test_create_ticket_persists_authenticated_client_id(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    response = client.post("/api/v1/tickets", json=_valid_payload(), headers=_auth_headers())

    assert response.status_code == 201
    assert fake_db.tickets_by_ticket_id["12345678"].client_id == "client-internal-id"


def test_create_ticket_echoes_x_request_id(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tickets",
        json=_valid_payload(),
        headers=_auth_headers({"X-Request-Id": "7f520de6-46d7-41c9-9978-9b4788335977"}),
    )

    assert response.status_code == 201
    assert response.headers["X-Request-Id"] == "7f520de6-46d7-41c9-9978-9b4788335977"


def test_create_ticket_max_length_ticket_id_succeeds(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    ticket_id = "A" * 50

    response = client.post(
        "/api/v1/tickets",
        json=_valid_payload(ticket_id=ticket_id),
        headers=_auth_headers(),
    )

    assert response.status_code == 201
    assert response.json() == {"ticketId": ticket_id}
    assert ticket_id in fake_db.tickets_by_ticket_id


def test_create_ticket_too_long_ticket_id_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tickets",
        json=_valid_payload(ticket_id="A" * 51),
        headers=_auth_headers(),
    )

    assert response.status_code == 422


def test_create_ticket_future_created_date_time_returns_422(client: TestClient) -> None:
    payload = _valid_payload()
    future = datetime.now(timezone.utc) + timedelta(days=1)
    payload["ticketDetails"]["createdDateTime"] = future.strftime("%Y-%m-%d %H:%M:%S")

    response = client.post("/api/v1/tickets", json=payload, headers=_auth_headers())

    assert response.status_code == 422


def test_create_ticket_latitude_boundary_90_succeeds(client: TestClient) -> None:
    payload = _valid_payload()
    payload["locationDetails"]["latitude"] = 90

    response = client.post("/api/v1/tickets", json=payload, headers=_auth_headers())

    assert response.status_code == 201


def test_create_ticket_latitude_over_max_returns_422(client: TestClient) -> None:
    payload = _valid_payload()
    payload["locationDetails"]["latitude"] = "90.000001"

    response = client.post("/api/v1/tickets", json=payload, headers=_auth_headers())

    assert response.status_code == 422


def test_create_ticket_longitude_boundary_180_succeeds(client: TestClient) -> None:
    payload = _valid_payload()
    payload["locationDetails"]["longitude"] = 180

    response = client.post("/api/v1/tickets", json=payload, headers=_auth_headers())

    assert response.status_code == 201


def test_create_ticket_longitude_over_max_returns_422(client: TestClient) -> None:
    payload = _valid_payload()
    payload["locationDetails"]["longitude"] = "180.000001"

    response = client.post("/api/v1/tickets", json=payload, headers=_auth_headers())

    assert response.status_code == 422


def test_create_ticket_empty_animal_name_returns_422(client: TestClient) -> None:
    payload = _valid_payload()
    payload["animals"] = [{"animalName": "", "breedName": "HF"}]

    response = client.post("/api/v1/tickets", json=payload, headers=_auth_headers())

    assert response.status_code == 422


def test_create_ticket_allows_duplicate_animals(
    client: TestClient,
    fake_db: _FakeSession,
) -> None:
    # The API contract defines no uniqueness rule for animals, so identical
    # entries are accepted and both persisted.
    payload = _valid_payload()
    payload["animals"] = [
        {"animalName": "Cow", "breedName": "HF"},
        {"animalName": "Cow", "breedName": "HF"},
    ]

    response = client.post("/api/v1/tickets", json=payload, headers=_auth_headers())

    assert response.status_code == 201
    assert len(fake_db.animals) == 2


def test_persistence_rolls_back_on_integrity_error(fake_db: _FakeSession) -> None:
    fake_db.commit_error = IntegrityError("INSERT", {}, Exception("duplicate ticket_id"))
    request = TicketCreateRequest.model_validate(_valid_payload())

    with pytest.raises(DuplicateTicketError):
        asyncio.run(
            ticket_crud.create_with_animals(
                fake_db,
                obj_in=request,
                client_id="client-internal-id",
            )
        )

    assert fake_db.rollbacks == 1
    assert fake_db.tickets_by_ticket_id == {}
    assert fake_db.animals == []


def test_persistence_rolls_back_when_animal_insert_fails(fake_db: _FakeSession) -> None:
    fake_db.commit_error = RuntimeError("animal insert failed")
    request = TicketCreateRequest.model_validate(_valid_payload())

    with pytest.raises(RuntimeError):
        asyncio.run(
            ticket_crud.create_with_animals(
                fake_db,
                obj_in=request,
                client_id="client-internal-id",
            )
        )

    assert fake_db.rollbacks == 1
    assert fake_db.tickets_by_ticket_id == {}
    assert fake_db.animals == []
