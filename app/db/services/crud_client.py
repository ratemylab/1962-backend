from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_token, hash_token
from app.db.models.client_model import ClientDB
from app.db.services.crud_base import CRUDBase
from app.schema.client import ClientCreate, ClientUpdate


class DuplicateClientError(Exception):
    pass


@dataclass(frozen=True)
class ClientPlaintextCredential:
    client_id: str
    client_name: str
    api_token: str


class CRUDClient(CRUDBase[ClientDB, ClientCreate, ClientUpdate]):
    async def get_by_client_id(self, db: AsyncSession, client_id: str) -> ClientDB | None:
        result = await db.execute(select(self.model).where(self.model.client_id == client_id))
        return result.scalar_one_or_none()

    async def create_client(
        self,
        db: AsyncSession,
        *,
        client_id: str,
        client_name: str,
        is_active: bool = True,
    ) -> ClientPlaintextCredential:
        """Single source of truth for client creation.

        Generates the API token, stores only its hash, and persists the client.
        The plaintext token is returned to the caller and never stored.
        """
        token = generate_token()
        db.add(
            ClientDB(
                client_id=client_id,
                client_name=client_name,
                hashed_token=hash_token(token),
                is_active=is_active,
            )
        )
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise DuplicateClientError from exc

        return ClientPlaintextCredential(
            client_id=client_id,
            client_name=client_name,
            api_token=token,
        )

    async def update_hashed_token(
        self,
        db: AsyncSession,
        *,
        client: ClientDB,
        hashed_token: str,
    ) -> ClientDB:
        """Persist a new token hash for an existing client.

        Token generation and hashing stay in the service layer; this method only
        updates the stored hash so the previous token stops authenticating.
        """
        client.hashed_token = hashed_token
        db.add(client)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        await db.refresh(client)
        return client


client_crud = CRUDClient(ClientDB)
