from __future__ import annotations

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ClientDB
from app.db.services.crud_ticket import DuplicateTicketError, ticket_crud
from app.exceptions.base import ApplicationException
from app.schema.ticket import (
    TicketCreateRequest,
    TicketCreateResponse,
    TicketUpdateRequest,
    TicketUpdateResponse,
)


class TicketService:
    async def create_ticket(
        self,
        db: AsyncSession,
        *,
        request: TicketCreateRequest,
        current_client: ClientDB,
    ) -> TicketCreateResponse:
        existing_ticket = await ticket_crud.get_by_ticket_id(db, request.ticket_id)
        if existing_ticket is not None:
            raise ApplicationException(
                message="Ticket already exists",
                status_code=status.HTTP_409_CONFLICT,
            )

        try:
            ticket = await ticket_crud.create_with_animals(
                db,
                obj_in=request,
                client_id=current_client.id,
            )
        except DuplicateTicketError as exc:
            raise ApplicationException(
                message="Ticket already exists",
                status_code=status.HTTP_409_CONFLICT,
            ) from exc

        return TicketCreateResponse(ticketId=ticket.ticket_id)

    async def update_ticket(
        self,
        db: AsyncSession,
        *,
        ticket_id: str,
        request: TicketUpdateRequest,
        current_client: ClientDB,
    ) -> TicketUpdateResponse:
        if request.ticket_id != ticket_id:
            raise ApplicationException(
                message="ticketId in the path and body must match",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        ticket = await ticket_crud.get_by_ticket_id(db, ticket_id)
        if ticket is None:
            raise ApplicationException(
                message="Ticket not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if ticket.client_id != current_client.id:
            raise ApplicationException(
                message="Client is not permitted to update this ticket",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        updated_ticket = await ticket_crud.update_ticket(db, ticket=ticket, obj_in=request)
        return TicketUpdateResponse(ticketId=updated_ticket.ticket_id)


ticket_service = TicketService()


def get_ticket_service() -> TicketService:
    return ticket_service
