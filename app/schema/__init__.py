"""Pydantic schemas for shared API contracts."""

from app.schema.animal import AnimalBase, AnimalRead
from app.schema.audio import AudioFileBase, AudioFileRead
from app.schema.auth import (
    AdminLoginRequest,
    AdminLoginResponse,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from app.schema.base import AppSchema, ClientIdString, NonEmptyString, TimestampedSchema
from app.schema.client import (
    ClientBase,
    ClientCreate,
    ClientCreateRequest,
    ClientCreateResponse,
    ClientRead,
    ClientTokenRotationRequest,
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
    "AdminLoginRequest",
    "AdminLoginResponse",
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
    "ClientTokenRotationRequest",
    "ClientTokenRotationResponse",
    "ClientUpdate",
    "LogoutResponse",
    "NonEmptyString",
    "RefreshTokenRequest",
    "RefreshTokenResponse",
    "TimestampedSchema",
    "TicketCreateRequest",
    "TicketCreateResponse",
    "TicketUpdateRequest",
    "TicketUpdateResponse",
]
