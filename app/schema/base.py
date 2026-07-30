from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
)

# API Contract v3.2: every DateTime field is exchanged as a UTC wall-clock
# string in this exact format (no timezone suffix, no fractional seconds).
CONTRACT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
CONTRACT_DATETIME_LABEL = "YYYY-MM-DD HH:mm:ss"
CONTRACT_DATETIME_EXAMPLE = "2026-07-22 08:25:53"
CONTRACT_DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"


def parse_contract_datetime(value: object) -> datetime:
    """Parse a contract datetime string strictly, rejecting ISO-8601 input.

    A ``datetime`` instance is accepted (and normalised to UTC) so the type can
    also be populated from ORM objects when serialising responses.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if not isinstance(value, str):
        raise ValueError(f"must use format {CONTRACT_DATETIME_LABEL} (UTC)")
    try:
        parsed = datetime.strptime(value, CONTRACT_DATETIME_FORMAT)
    except ValueError as exc:
        raise ValueError(f"must use format {CONTRACT_DATETIME_LABEL} (UTC)") from exc
    return parsed.replace(tzinfo=timezone.utc)


def serialize_contract_datetime(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.strftime(CONTRACT_DATETIME_FORMAT)


# Reusable field type that enforces the contract format on input and output and
# documents itself as a plain string (not ISO-8601 ``date-time``) in OpenAPI.
ContractDateTime = Annotated[
    datetime,
    BeforeValidator(parse_contract_datetime),
    PlainSerializer(serialize_contract_datetime, return_type=str),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": CONTRACT_DATETIME_PATTERN,
            "example": CONTRACT_DATETIME_EXAMPLE,
        }
    ),
]


class AppSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")


class TimestampedSchema(AppSchema):
    created_at: datetime | None = None
    updated_at: datetime | None = None


NonEmptyString = Annotated[str, Field(min_length=1)]
ClientIdString = Annotated[str, Field(min_length=1, max_length=100)]
TicketIdString = Annotated[str, Field(min_length=1, max_length=50)]
Latitude = Annotated[Decimal, Field(ge=-90, le=90, decimal_places=6)]
Longitude = Annotated[Decimal, Field(ge=-180, le=180, decimal_places=6)]
