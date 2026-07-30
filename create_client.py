from __future__ import annotations

import argparse
import asyncio
import secrets

from sqlalchemy import select

from app.db.models import ClientDB
from app.db.seed import create_client
from app.db.session import AsyncSessionFactory


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create an API client and print its one-time token.")
    parser.add_argument("--client-id", help="Public client identifier. Generated when omitted.")
    parser.add_argument("--client-name", required=True, help="Human-readable client name.")
    parser.add_argument("--inactive", action="store_true", help="Create the client as inactive.")
    return parser


def _generate_client_id() -> str:
    return f"client_{secrets.token_hex(6)}"


async def _create(args: argparse.Namespace) -> None:
    client_id = args.client_id or _generate_client_id()
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(ClientDB).where(ClientDB.client_id == client_id))
        if result.scalar_one_or_none() is not None:
            raise SystemExit(f"Client ID already exists: {client_id}")

        credential = await create_client(
            session,
            client_id=client_id,
            client_name=args.client_name,
            is_active=not args.inactive,
        )

    print("Client created. Store this plaintext token securely; it will not be shown again.")
    print(f"client_id={credential.client_id}")
    print(f"client_name={credential.client_name}")
    print(f"api_token={credential.api_token}")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(_create(args))


if __name__ == "__main__":
    main()
