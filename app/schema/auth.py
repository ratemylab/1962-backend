from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.core.security import MAX_PASSWORD_BYTES

BEARER_TOKEN_TYPE = "Bearer"
LOGOUT_MESSAGE = "Logged out successfully"


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "username": "admin",
                "password": "Admin@123",
            }
        },
    )

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=MAX_PASSWORD_BYTES)


class AdminLoginResponse(BaseModel):
    """Login result.

    The refresh token is returned exactly once here; only its hash is stored,
    and the password hash is never exposed.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "accessToken": "signed.jwt.token",
                "refreshToken": "opaque-refresh-token",
                "tokenType": BEARER_TOKEN_TYPE,
                "expiresIn": 3600,
                "refreshExpiresIn": 604800,
            }
        },
    )

    access_token: str = Field(..., alias="accessToken")
    refresh_token: str = Field(..., alias="refreshToken")
    token_type: str = Field(default=BEARER_TOKEN_TYPE, alias="tokenType")
    expires_in: int = Field(..., alias="expiresIn")
    refresh_expires_in: int = Field(..., alias="refreshExpiresIn")


class RefreshTokenRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        json_schema_extra={"example": {"refreshToken": "opaque-refresh-token"}},
    )

    refresh_token: str = Field(..., alias="refreshToken", min_length=1, max_length=512)


class RefreshTokenResponse(BaseModel):
    """A renewed access token. The refresh token itself is left unchanged."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "accessToken": "signed.jwt.token",
                "tokenType": BEARER_TOKEN_TYPE,
                "expiresIn": 3600,
            }
        },
    )

    access_token: str = Field(..., alias="accessToken")
    token_type: str = Field(default=BEARER_TOKEN_TYPE, alias="tokenType")
    expires_in: int = Field(..., alias="expiresIn")


class LogoutResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={"example": {"message": LOGOUT_MESSAGE}},
    )

    message: str = Field(default=LOGOUT_MESSAGE)
