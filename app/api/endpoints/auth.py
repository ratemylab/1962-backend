from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import INVALID_ADMIN_TOKEN_DESCRIPTION, get_current_admin
from app.db.models import AdminDB
from app.db.session import get_db
from app.schema.auth import (
    AdminLoginRequest,
    AdminLoginResponse,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from app.services.auth_service import AuthService, get_auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


LOGIN_ERROR_RESPONSES = {
    400: {"description": "Malformed JSON or missing mandatory field."},
    401: {"description": "Unknown username, incorrect password, or a deactivated admin."},
    422: {"description": "Field validation failed."},
    500: {"description": "Unexpected server-side error."},
}

LOGIN_DESCRIPTION = (
    "Authenticates an administrator and returns a JWT access token plus an "
    "opaque refresh token. Send the access token as "
    "`Authorization: Bearer <accessToken>` when calling admin endpoints, and "
    "exchange the refresh token at `/auth/refresh` once it expires. Only the "
    "newest login stays valid: logging in again invalidates the previous "
    "refresh token. Client APIs are unaffected and keep using X-Client-Id and "
    "X-Api-Token."
)

REFRESH_ERROR_RESPONSES = {
    400: {"description": "Malformed JSON or missing mandatory field."},
    401: {
        "description": (
            "Unknown, revoked or expired refresh token, or a deactivated admin."
        )
    },
    422: {"description": "Field validation failed."},
    500: {"description": "Unexpected server-side error."},
}

REFRESH_DESCRIPTION = (
    "Exchanges a valid refresh token for a new access token without resending "
    "credentials. The refresh token is not rotated and stays usable until the "
    "admin logs in again, logs out, or it expires."
)

LOGOUT_ERROR_RESPONSES = {
    401: {"description": INVALID_ADMIN_TOKEN_DESCRIPTION},
    500: {"description": "Unexpected server-side error."},
}

LOGOUT_DESCRIPTION = (
    "Revokes the authenticated admin's refresh token, so `/auth/refresh` stops "
    "working for it. Already-issued access tokens remain valid until they "
    "expire. Repeated logouts are idempotent."
)


@router.post(
    "/login",
    response_model=AdminLoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Admin login",
    description=LOGIN_DESCRIPTION,
    responses=LOGIN_ERROR_RESPONSES,
)
async def login(
    body: AdminLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> AdminLoginResponse:
    return await auth_service.login(db, request=body)


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh admin access token",
    description=REFRESH_DESCRIPTION,
    responses=REFRESH_ERROR_RESPONSES,
)
async def refresh(
    body: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> RefreshTokenResponse:
    return await auth_service.refresh(db, request=body)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Admin logout",
    description=LOGOUT_DESCRIPTION,
    responses=LOGOUT_ERROR_RESPONSES,
)
async def logout(
    current_admin: Annotated[AdminDB, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> LogoutResponse:
    return await auth_service.logout(db, current_admin=current_admin)
