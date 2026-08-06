from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.seed import seed_admin, seed_clients
from app.db.session import AsyncSessionFactory


async def _seed_default_admin(session: AsyncSession) -> None:
    admin = await seed_admin(session)
    if admin is None:
        print(f"Admin {settings.seed_admin_username!r} already exists; not modified.")
        return

    # The password is intentionally not printed; only its bcrypt hash is stored.
    print(
        f"Default admin {admin.username!r} created with the configured "
        "SEED_ADMIN_PASSWORD. Change it before exposing this deployment."
    )


async def main() -> None:
    async with AsyncSessionFactory() as session:
        if settings.seed_admin_enabled:
            await _seed_default_admin(session)
        credentials = await seed_clients(session)

    if not credentials:
        print("Seed clients already exist; no plaintext tokens generated.")
        return

    print("Seed clients created. Store these plaintext tokens securely; they will not be shown again.")
    for credential in credentials:
        print(
            f"client_id={credential.client_id} "
            f"client_name={credential.client_name!r} "
            f"api_token={credential.api_token}"
        )


if __name__ == "__main__":
    asyncio.run(main())
