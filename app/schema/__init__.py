"""Pydantic schemas for shared API contracts."""

from app.schema.animal import AnimalBase, AnimalRead
from app.schema.audio import AudioFileBase, AudioFileRead
from app.schema.base import AppSchema, ClientIdString, NonEmptyString, TimestampedSchema
from app.schema.client import (
    ClientBase,
    ClientCreate,
    ClientCreateRequest,
    ClientCreateResponse,
    ClientRead,
    ClientTokenRotationResponse,
    ClientUpdate,
)
from app.schema.ticket import (
    TicketCreateRequest,
    TicketCreateResponse,
    TicketUpdateRequest,
    TicketUpdateResponse,
)

__all__ = [
    "AnimalBase",
    "AnimalRead",
    "AppSchema",
    "AudioFileBase",
    "AudioFileRead",
    "ClientBase",
    "ClientCreate",
    "ClientCreateRequest",
    "ClientCreateResponse",
    "ClientIdString",
    "ClientRead",
    "ClientTokenRotationResponse",
    "ClientUpdate",
    "NonEmptyString",
    "TimestampedSchema",
    "TicketCreateRequest",
    "TicketCreateResponse",
    "TicketUpdateRequest",
    "TicketUpdateResponse",
]
