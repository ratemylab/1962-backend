from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_token
from app.db.models import ClientDB
from app.db.session import get_db


INVALID_CLIENT_CREDENTIALS = "Invalid client credentials"
MISSING_AUTH_HEADERS = "Missing required authentication headers."
EMPTY_AUTH_HEADERS = "Authentication headers cannot be empty."

# OpenAPI descriptions for the failure modes of get_current_client, shared by
# every endpoint that depends on it.
INVALID_CREDENTIALS_DESCRIPTION = (
    "Invalid or inactive client credentials: unknown X-Client-Id, incorrect "
    "X-Api-Token, or a deactivated client."
)
MALFORMED_AUTH_HEADERS_DESCRIPTION = (
    "missing or malformed X-Client-Id / X-Api-Token authentication headers"
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
