from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnimalDB, TicketDB
from app.schema.ticket import TicketCreateRequest, TicketUpdateRequest


class DuplicateTicketError(Exception):
    pass


class CRUDTicket:
    async def get_by_ticket_id(self, db: AsyncSession, ticket_id: str) -> TicketDB | None:
        result = await db.execute(select(TicketDB).where(TicketDB.ticket_id == ticket_id))
        return result.scalar_one_or_none()

    async def create_with_animals(
        self,
        db: AsyncSession,
        *,
        obj_in: TicketCreateRequest,
        client_id: str,
    ) -> TicketDB:
        ticket = TicketDB(
            ticket_id=obj_in.ticket_id,
            client_id=client_id,
            ticket_status=obj_in.ticket_details.ticket_status,
            type=obj_in.ticket_details.type,
            created_date_time=obj_in.ticket_details.created_date_time,
            closed_date_time=None,
            farmer_id=obj_in.farmer_details.farmer_id,
            farmer_name=obj_in.farmer_details.farmer_name,
            village_id=obj_in.location_details.village_id,
            village=obj_in.location_details.village,
            panchayat_id=obj_in.location_details.panchayat_id,
            panchayat=obj_in.location_details.panchayat,
            block_id=obj_in.location_details.block_id,
            block=obj_in.location_details.block,
            district=obj_in.location_details.district,
            state=obj_in.location_details.state,
            latitude=obj_in.location_details.latitude,
            longitude=obj_in.location_details.longitude,
            disease=obj_in.disease_treatment_details.disease,
            symptoms=obj_in.disease_treatment_details.symptoms,
            treatment_given=None,
        )
        ticket.animals = [
            AnimalDB(
                animal_name=animal.animal_name,
                breed_name=animal.breed_name,
            )
            for animal in obj_in.animals
        ]

        db.add(ticket)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise DuplicateTicketError from exc
        except Exception:
            await db.rollback()
            raise

        await db.refresh(ticket)
        return ticket

    async def update_ticket(
        self,
        db: AsyncSession,
        *,
        ticket: TicketDB,
        obj_in: TicketUpdateRequest,
    ) -> TicketDB:
        ticket.ticket_status = obj_in.ticket_details.ticket_status
        ticket.closed_date_time = obj_in.ticket_details.closed_date_time

        ticket.doctor_id = obj_in.mvu_details.doctor_id
        ticket.doctor_name = obj_in.mvu_details.doctor_name
        ticket.paravet_id = obj_in.mvu_details.paravet_id
        ticket.paravet_name = obj_in.mvu_details.paravet_name
        ticket.mvu_number = obj_in.mvu_details.mvu_number

        ticket.disease = obj_in.disease_treatment_details.disease
        # symptoms may be omitted/null/empty to indicate "unchanged" (contract 4.3.4)
        if obj_in.disease_treatment_details.symptoms:
            ticket.symptoms = obj_in.disease_treatment_details.symptoms
        if obj_in.disease_treatment_details.treatment_given is not None:
            ticket.treatment_given = obj_in.disease_treatment_details.treatment_given

        db.add(ticket)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        await db.refresh(ticket)
        return ticket


ticket_crud = CRUDTicket()
