from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AudioFileDB


class DuplicateAudioError(Exception):
    pass


class CRUDAudio:
    async def get_by_ticket_pk(self, db: AsyncSession, ticket_pk: str) -> AudioFileDB | None:
        result = await db.execute(
            select(AudioFileDB).where(AudioFileDB.ticket_id == ticket_pk)
        )
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, audio_file: AudioFileDB) -> AudioFileDB:
        db.add(audio_file)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise DuplicateAudioError from exc
        except Exception:
            await db.rollback()
            raise

        await db.refresh(audio_file)
        return audio_file


audio_crud = CRUDAudio()
