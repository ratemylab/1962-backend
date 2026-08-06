from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.admin_model import AdminDB


class DuplicateAdminError(Exception):
    pass


class CRUDAdmin:
    async def get_by_username(self, db: AsyncSession, username: str) -> AdminDB | None:
        result = await db.execute(select(AdminDB).where(AdminDB.username == username))
        return result.scalar_one_or_none()

    async def get_by_id(self, db: AsyncSession, admin_id: str) -> AdminDB | None:
        result = await db.execute(select(AdminDB).where(AdminDB.id == admin_id))
        return result.scalar_one_or_none()

    async def create_admin(
        self,
        db: AsyncSession,
        *,
        username: str,
        password_hash: str,
        is_active: bool = True,
    ) -> AdminDB:
        """Persist an admin account. Only the bcrypt hash is ever stored."""
        admin = AdminDB(
            username=username,
            password_hash=password_hash,
            is_active=is_active,
        )
        db.add(admin)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise DuplicateAdminError from exc
        except Exception:
            await db.rollback()
            raise

        await db.refresh(admin)
        return admin


admin_crud = CRUDAdmin()
