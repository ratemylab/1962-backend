from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    INVALID_CREDENTIALS_DESCRIPTION,
    MALFORMED_AUTH_HEADERS_DESCRIPTION,
    get_current_client,
)
from app.db.models import ClientDB
from app.db.session import get_db
from app.schema.client import (
    ClientCreateRequest,
    ClientCreateResponse,
    ClientTokenRotationResponse,
)
from app.services.admin_service import AdminService, get_admin_service


router = APIRouter(prefix="/admin", tags=["admin"])


CREATE_CLIENT_ERROR_RESPONSES = {
    409: {"description": "A client with the supplied clientId already exists."},
    422: {"description": "Field validation failed."},
    500: {"description": "Unexpected server-side error."},
}

ROTATE_TOKEN_ERROR_RESPONSES = {
    400: {"description": f"Request contains {MALFORMED_AUTH_HEADERS_DESCRIPTION}."},
    401: {"description": INVALID_CREDENTIALS_DESCRIPTION},
    500: {"description": "Unexpected server-side error."},
}

ROTATE_TOKEN_DESCRIPTION = (
    "Rotates the authenticated client's API token. The existing token becomes "
    "invalid immediately after successful rotation. The newly generated token is "
    "returned only once and must be stored securely by the client."
)


@router.post(
    "/clients",
    response_model=ClientCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API client",
    responses=CREATE_CLIENT_ERROR_RESPONSES,
)
async def create_client(
    body: ClientCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
    admin_service: AdminService = Depends(get_admin_service),
) -> ClientCreateResponse:
    return await admin_service.create_client(db, request=body)


@router.post(
    "/clients/rotate-token",
    response_model=ClientTokenRotationResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate API Token",
    description=ROTATE_TOKEN_DESCRIPTION,
    responses=ROTATE_TOKEN_ERROR_RESPONSES,
)
async def rotate_token(
    current_client: Annotated[ClientDB, Depends(get_current_client)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
    admin_service: AdminService = Depends(get_admin_service),
) -> ClientTokenRotationResponse:
    return await admin_service.rotate_token(db, current_client=current_client)
