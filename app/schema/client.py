from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schema.base import AppSchema, ClientIdString, TimestampedSchema


class ClientBase(AppSchema):
    client_id: ClientIdString
    client_name: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True


class ClientCreate(ClientBase):
    hashed_token: str = Field(..., min_length=1, max_length=255)


class ClientCreateRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "clientId": "client_up_001",
                "clientName": "Field App - Uttar Pradesh",
            }
        },
    )

    client_id: str = Field(..., alias="clientId", min_length=1, max_length=100)
    client_name: str = Field(..., alias="clientName", min_length=1, max_length=255)


class ClientCreateResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "clientId": "client_up_001",
                "clientName": "Field App - Uttar Pradesh",
                "apiToken": "generated_plaintext_api_token",
            }
        },
    )

    client_id: str = Field(..., alias="clientId")
    client_name: str = Field(..., alias="clientName")
    api_token: str = Field(..., alias="apiToken")


TOKEN_ROTATION_MESSAGE = (
    "API token rotated successfully. Store this token securely. "
    "It will not be shown again."
)


class ClientTokenRotationResponse(BaseModel):
    """Rotation result. Exposes the plaintext token once and never the stored hash."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "clientId": "client_rj_001",
                "clientName": "Field App - Rajasthan",
                "apiToken": "new_generated_plaintext_api_token",
                "message": TOKEN_ROTATION_MESSAGE,
            }
        },
    )

    client_id: str = Field(..., alias="clientId")
    client_name: str = Field(..., alias="clientName")
    api_token: str = Field(..., alias="apiToken")
    message: str = TOKEN_ROTATION_MESSAGE


class ClientUpdate(AppSchema):
    id: str
    client_name: str | None = Field(default=None, min_length=1, max_length=255)
    hashed_token: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


class ClientRead(ClientBase, TimestampedSchema):
    id: str
