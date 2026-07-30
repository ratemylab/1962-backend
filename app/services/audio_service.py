from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import AudioFileDB, ClientDB
from app.db.services.crud_audio import DuplicateAudioError, audio_crud
from app.db.services.crud_ticket import ticket_crud
from app.exceptions.base import ApplicationException
from app.schema.audio import AudioUploadResponse

ALLOWED_AUDIO_EXTENSIONS = {".ogg", ".mp3", ".wav", ".m4a"}
MAX_AUDIO_UPLOAD_BYTES = 10 * 1024 * 1024


class AudioService:
    def __init__(self, upload_dir: Path | None = None) -> None:
        self._upload_dir = upload_dir

    @property
    def upload_dir(self) -> Path:
        return self._upload_dir if self._upload_dir is not None else settings.audio_upload_path

    async def upload_audio(
        self,
        db: AsyncSession,
        *,
        ticket_id: str,
        upload: UploadFile,
        current_client: ClientDB,
    ) -> AudioUploadResponse:
        ticket = await ticket_crud.get_by_ticket_id(db, ticket_id)
        if ticket is None:
            raise ApplicationException(
                message="Ticket not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if ticket.client_id != current_client.id:
            raise ApplicationException(
                message="Client is not permitted to upload audio for this ticket",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        existing_audio = await audio_crud.get_by_ticket_pk(db, ticket.id)
        if existing_audio is not None:
            raise ApplicationException(
                message="An audio file has already been uploaded for this ticket",
                status_code=status.HTTP_409_CONFLICT,
            )

        original_filename = upload.filename or ""
        if ticket_id not in original_filename:
            raise ApplicationException(
                message="Filename must include the ticketId for traceability",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        extension = Path(original_filename).suffix.lower()
        if extension not in ALLOWED_AUDIO_EXTENSIONS:
            raise ApplicationException(
                message="Unsupported audio file format",
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )

        content = await upload.read()
        if len(content) > MAX_AUDIO_UPLOAD_BYTES:
            raise ApplicationException(
                message="Uploaded file exceeds the 10 MB size limit",
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        audio_file_id = f"af-{uuid4().hex[:8]}"
        storage_path = self._write_file(audio_file_id, extension, content)
        uploaded_at = datetime.now(timezone.utc)

        try:
            audio_row = await audio_crud.create(
                db,
                AudioFileDB(
                    ticket_id=ticket.id,
                    client_id=current_client.id,
                    audio_file_id=audio_file_id,
                    file_name=original_filename,
                    storage_path=str(storage_path),
                    uploaded_at=uploaded_at,
                ),
            )
        except DuplicateAudioError as exc:
            self._remove_file(storage_path)
            raise ApplicationException(
                message="An audio file has already been uploaded for this ticket",
                status_code=status.HTTP_409_CONFLICT,
            ) from exc
        except Exception:
            # Roll back the filesystem side-effect so no orphaned file remains.
            self._remove_file(storage_path)
            raise

        return AudioUploadResponse(
            ticketId=ticket.ticket_id,
            audioFileId=audio_row.audio_file_id,
            fileName=audio_row.file_name,
            uploadedAt=uploaded_at,
        )

    def _write_file(self, audio_file_id: str, extension: str, content: bytes) -> Path:
        upload_dir = self.upload_dir
        upload_dir.mkdir(parents=True, exist_ok=True)
        storage_path = upload_dir / f"{audio_file_id}{extension}"
        try:
            # exclusive creation guarantees we never overwrite an existing file
            with open(storage_path, "xb") as buffer:
                buffer.write(content)
        except FileExistsError as exc:
            raise ApplicationException(
                message="Storage filename collision; please retry",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc
        except OSError:
            self._remove_file(storage_path)
            raise
        return storage_path

    @staticmethod
    def _remove_file(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


audio_service = AudioService()


def get_audio_service() -> AudioService:
    return audio_service
