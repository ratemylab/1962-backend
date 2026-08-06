from __future__ import annotations

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_token, hash_token
from app.db.services.crud_client import DuplicateClientError, client_crud
from app.exceptions.base import ApplicationException
from app.schema.client import (
    ClientCreateRequest,
    ClientCreateResponse,
    ClientTokenRotationRequest,
    ClientTokenRotationResponse,
)


class AdminService:
    async def create_client(
        self,
        db: AsyncSession,
        *,
        request: ClientCreateRequest,
    ) -> ClientCreateResponse:
        existing_client = await client_crud.get_by_client_id(db, request.client_id)
        if existing_client is not None:
            raise ApplicationException(
                message="Client already exists",
                status_code=status.HTTP_409_CONFLICT,
            )

        try:
            credential = await client_crud.create_client(
                db,
                client_id=request.client_id,
                client_name=request.client_name,
            )
        except DuplicateClientError as exc:
            raise ApplicationException(
                message="Client already exists",
                status_code=status.HTTP_409_CONFLICT,
            ) from exc

        return ClientCreateResponse(
            clientId=credential.client_id,
            clientName=credential.client_name,
            apiToken=credential.api_token,
        )

    async def rotate_token(
        self,
        db: AsyncSession,
        *,
        request: ClientTokenRotationRequest,
    ) -> ClientTokenRotationResponse:
        """Rotate the API token of the client named in the request.

        The caller is an authenticated admin, so the target client is taken
        from the request body rather than from the credentials.
        """
        client = await client_crud.get_by_client_id(db, request.client_id)
        if client is None:
            raise ApplicationException(
                message="Client not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        new_token = generate_token()
        rotated_client = await client_crud.update_hashed_token(
            db,
            client=client,
            hashed_token=hash_token(new_token),
        )

        return ClientTokenRotationResponse(
            clientId=rotated_client.client_id,
            clientName=rotated_client.client_name,
            apiToken=new_token,
        )


admin_service = AdminService()


def get_admin_service() -> AdminService:
    return admin_service
