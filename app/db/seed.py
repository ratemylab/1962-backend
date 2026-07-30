from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ClientDB
from app.db.services.crud_client import ClientPlaintextCredential, client_crud


DEFAULT_SEED_CLIENTS: tuple[tuple[str, str], ...] = (
    ("client_rj_001", "Field App - Rajasthan"),
    ("client_gj_001", "Field App - Gujarat"),
    ("client_partner_01", "Partner Clinic Integration"),
    ("client_qa_001", "Internal QA / Test Client"),
)


async def create_client(
    db: AsyncSession,
    *,
    client_id: str,
    client_name: str,
    is_active: bool = True,
) -> ClientPlaintextCredential:
    """Thin wrapper kept for the seed process and create_client.py CLI.

    Delegates to the single client-creation implementation in the CRUD layer.
    """
    return await client_crud.create_client(
        db,
        client_id=client_id,
        client_name=client_name,
        is_active=is_active,
    )


async def seed_clients(db: AsyncSession) -> list[ClientPlaintextCredential]:
    created_credentials: list[ClientPlaintextCredential] = []
    for client_id, client_name in DEFAULT_SEED_CLIENTS:
        result = await db.execute(select(ClientDB).where(ClientDB.client_id == client_id))
        if result.scalar_one_or_none() is not None:
            continue

        created_credentials.append(
            await create_client(
                db,
                client_id=client_id,
                client_name=client_name,
            )
        )
    return created_credentials
