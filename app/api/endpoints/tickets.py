from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, Path, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    INVALID_CREDENTIALS_DESCRIPTION,
    MALFORMED_AUTH_HEADERS_DESCRIPTION,
    get_current_client,
)
from app.db.models import ClientDB
from app.db.session import get_db
from app.schema.audio import AudioUploadResponse
from app.schema.ticket import (
    TicketCreateRequest,
    TicketCreateResponse,
    TicketUpdateRequest,
    TicketUpdateResponse,
)
from app.services.audio_service import AudioService, get_audio_service
from app.services.ticket_service import TicketService, get_ticket_service


router = APIRouter(prefix="/tickets", tags=["tickets"])


ERROR_RESPONSES = {
    400: {
        "description": (
            "Malformed JSON, missing mandatory field, invalid field format, or "
            f"{MALFORMED_AUTH_HEADERS_DESCRIPTION}."
        )
    },
    401: {"description": INVALID_CREDENTIALS_DESCRIPTION},
    403: {"description": "Client is not permitted to perform this operation."},
    409: {"description": "Resource already exists."},
    422: {"description": "Field validation failed."},
    500: {"description": "Unexpected server-side error."},
}

UPDATE_ERROR_RESPONSES = {
    400: {
        "description": (
            "Malformed JSON, missing mandatory field, invalid field format, or "
            f"{MALFORMED_AUTH_HEADERS_DESCRIPTION}."
        )
    },
    401: {"description": INVALID_CREDENTIALS_DESCRIPTION},
    403: {"description": "Client is not permitted to perform this operation."},
    404: {"description": "ticketId in the path does not match any existing ticket."},
    422: {"description": "Field validation failed."},
    500: {"description": "Unexpected server-side error."},
}

AUDIO_ERROR_RESPONSES = {
    400: {
        "description": (
            "Missing file, filename does not include the ticketId, or "
            f"{MALFORMED_AUTH_HEADERS_DESCRIPTION}."
        )
    },
    401: {"description": INVALID_CREDENTIALS_DESCRIPTION},
    403: {"description": "Client is not permitted to upload audio for this ticket."},
    404: {"description": "ticketId in the path does not match any existing ticket."},
    409: {"description": "An audio file has already been uploaded for this ticket."},
    413: {"description": "Uploaded file exceeds the 10 MB size limit."},
    415: {"description": "Unsupported audio file format."},
    500: {"description": "Unexpected server-side error."},
}


@router.post(
    "",
    response_model=TicketCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create ticket",
    responses=ERROR_RESPONSES,
)
async def create_ticket(
    body: TicketCreateRequest,
    current_client: Annotated[ClientDB, Depends(get_current_client)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
    ticket_service: TicketService = Depends(get_ticket_service),
) -> TicketCreateResponse:
    return await ticket_service.create_ticket(
        db,
        request=body,
        current_client=current_client,
    )


@router.put(
    "/{ticketId}",
    response_model=TicketUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update ticket",
    responses=UPDATE_ERROR_RESPONSES,
)
async def update_ticket(
    body: TicketUpdateRequest,
    current_client: Annotated[ClientDB, Depends(get_current_client)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ticket_id: Annotated[str, Path(alias="ticketId", max_length=50)],
    x_request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
    ticket_service: TicketService = Depends(get_ticket_service),
) -> TicketUpdateResponse:
    return await ticket_service.update_ticket(
        db,
        ticket_id=ticket_id,
        request=body,
        current_client=current_client,
    )


@router.post(
    "/{ticketId}/audio",
    response_model=AudioUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload ticket audio",
    responses=AUDIO_ERROR_RESPONSES,
)
async def upload_ticket_audio(
    current_client: Annotated[ClientDB, Depends(get_current_client)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ticket_id: Annotated[str, Path(alias="ticketId", max_length=50)],
    audio_file: Annotated[UploadFile, File(alias="audioFile")],
    x_request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
    audio_service: AudioService = Depends(get_audio_service),
) -> AudioUploadResponse:
    return await audio_service.upload_audio(
        db,
        ticket_id=ticket_id,
        upload=audio_file,
        current_client=current_client,
    )
