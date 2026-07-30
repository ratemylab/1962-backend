from __future__ import annotations

import asyncio

from app.db.seed import seed_clients
from app.db.session import AsyncSessionFactory


async def main() -> None:
    async with AsyncSessionFactory() as session:
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
