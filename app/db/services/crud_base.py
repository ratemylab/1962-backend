from __future__ import annotations

from typing import Any, Generic, TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.base_model import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: type[ModelType]) -> None:
        self.model = model

    async def get(self, db: AsyncSession, id: str) -> ModelType | None:
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        result = await db.execute(select(self.model).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_by_ids(self, db: AsyncSession, ids: list[str]) -> list[ModelType]:
        if not ids:
            return []
        result = await db.execute(select(self.model).where(self.model.id.in_(ids)))
        return list(result.scalars().all())

    async def get_count(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count()).select_from(self.model))
        return int(result.scalar_one())

    async def create(
        self,
        db: AsyncSession,
        obj_in: CreateSchemaType,
        *,
        flush_only: bool = False,
    ) -> ModelType:
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        if flush_only:
            await db.flush()
        else:
            await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        obj_in: UpdateSchemaType,
        *,
        flush_only: bool = False,
    ) -> ModelType:
        obj_data = obj_in.model_dump(exclude_unset=True)
        obj_id = obj_data.pop("id", None)
        if not obj_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="id is required for update",
            )

        db_obj = await self.get(db, obj_id)
        if db_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} not found",
            )

        for field, value in obj_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        if flush_only:
            await db.flush()
        else:
            await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, id: str) -> ModelType:
        db_obj = await self.get(db, id)
        if db_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} not found",
            )
        await db.delete(db_obj)
        await db.commit()
        return db_obj
