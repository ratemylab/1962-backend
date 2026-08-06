from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.refresh_token_model import RefreshTokenDB


class CRUDRefreshToken:
    async def get_by_admin_id(self, db: AsyncSession, admin_id: str) -> RefreshTokenDB | None:
        result = await db.execute(
            select(RefreshTokenDB).where(RefreshTokenDB.admin_id == admin_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hashed_token(
        self,
        db: AsyncSession,
        hashed_refresh_token: str,
    ) -> RefreshTokenDB | None:
        result = await db.execute(
            select(RefreshTokenDB).where(
                RefreshTokenDB.hashed_refresh_token == hashed_refresh_token
            )
        )
        return result.scalar_one_or_none()

    async def replace_for_admin(
        self,
        db: AsyncSession,
        *,
        admin_id: str,
        hashed_refresh_token: str,
        expires_at: datetime,
    ) -> RefreshTokenDB:
        """Store the admin's only refresh token, discarding any previous one.

        Token generation and hashing stay in the service layer; this method
        only persists the hash so the previous refresh token stops working.
        """
        refresh_token = await self.get_by_admin_id(db, admin_id)
        if refresh_token is None:
            refresh_token = RefreshTokenDB(
                admin_id=admin_id,
                hashed_refresh_token=hashed_refresh_token,
                expires_at=expires_at,
            )
        else:
            refresh_token.hashed_refresh_token = hashed_refresh_token
            refresh_token.expires_at = expires_at

        db.add(refresh_token)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        await db.refresh(refresh_token)
        return refresh_token

    async def delete_for_admin(self, db: AsyncSession, *, admin_id: str) -> bool:
        """Revoke the admin's refresh token. Returns False when none was stored."""
        refresh_token = await self.get_by_admin_id(db, admin_id)
        if refresh_token is None:
            return False

        await db.delete(refresh_token)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        return True


refresh_token_crud = CRUDRefreshToken()
