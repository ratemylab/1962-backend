from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schema.base import AppSchema, ContractDateTime, TimestampedSchema


class AudioFileBase(AppSchema):
    audio_file_id: str = Field(..., min_length=1, max_length=50)
    file_name: str = Field(..., min_length=1, max_length=255)
    storage_path: str = Field(..., min_length=1, max_length=500)


class AudioFileRead(AudioFileBase, TimestampedSchema):
    id: str
    ticket_id: str
    client_id: str
    uploaded_at: ContractDateTime


class AudioUploadResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticket_id: str = Field(..., alias="ticketId")
    audio_file_id: str = Field(..., alias="audioFileId")
    file_name: str = Field(..., alias="fileName")
    uploaded_at: ContractDateTime = Field(..., alias="uploadedAt")
