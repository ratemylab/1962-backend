from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_access_token, verify_token
from app.db.models import AdminDB, ClientDB
from app.db.services.crud_admin import admin_crud
from app.db.session import get_db


INVALID_CLIENT_CREDENTIALS = "Invalid client credentials"
MISSING_AUTH_HEADERS = "Missing required authentication headers."
EMPTY_AUTH_HEADERS = "Authentication headers cannot be empty."

INVALID_ADMIN_TOKEN = "Invalid or expired admin token"
MISSING_ADMIN_AUTHORIZATION = "Missing Bearer authorization header."

# OpenAPI descriptions for the failure modes of get_current_client, shared by
# every endpoint that depends on it.
INVALID_CREDENTIALS_DESCRIPTION = (
    "Invalid or inactive client credentials: unknown X-Client-Id, incorrect "
    "X-Api-Token, or a deactivated client."
)
MALFORMED_AUTH_HEADERS_DESCRIPTION = (
    "missing or malformed X-Client-Id / X-Api-Token authentication headers"
)

# OpenAPI description for the failure modes of get_current_admin.
INVALID_ADMIN_TOKEN_DESCRIPTION = (
    "Missing, malformed, expired or otherwise invalid admin Bearer token, or a "
    "deactivated admin account."
)

# auto_error is disabled so a missing or non-Bearer Authorization header is
# reported through the same handler and body shape as every other failure.
admin_bearer_scheme = HTTPBearer(
    scheme_name="AdminBearerAuth",
    description="JWT access token issued by POST /api/v1/auth/login.",
    auto_error=False,
)


async def get_current_client(
    db: Annotated[AsyncSession, Depends(get_db)],
    x_client_id: Annotated[str | None, Header(alias="X-Client-Id")] = None,
    x_api_token: Annotated[str | None, Header(alias="X-Api-Token")] = None,
) -> ClientDB:
    # Malformed request (400): the caller never supplied usable credentials.
    if x_client_id is None or x_api_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MISSING_AUTH_HEADERS,
        )

    if not x_client_id.strip() or not x_api_token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=EMPTY_AUTH_HEADERS,
        )

    # Authentication failure (401): unknown client, bad token, or inactive client.
    result = await db.execute(select(ClientDB).where(ClientDB.client_id == x_client_id.strip()))
    client = result.scalar_one_or_none()
    if client is None or not client.is_active or not verify_token(x_api_token, client.hashed_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CLIENT_CREDENTIALS,
        )

    return client


async def get_current_admin(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(admin_bearer_scheme)
    ] = None,
) -> AdminDB:
    """Authenticate an admin from the `Authorization: Bearer <JWT>` header.

    Used only by admin endpoints; client endpoints keep using
    get_current_client with X-Client-Id / X-Api-Token.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MISSING_ADMIN_AUTHORIZATION,
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = verify_access_token(credentials.credentials)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_ADMIN_TOKEN,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Re-read the account so deactivated admins stop authenticating immediately,
    # even while a previously issued token is still within its expiry window.
    admin = await admin_crud.get_by_username(db, username)
    if admin is None or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_ADMIN_TOKEN,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return admin
