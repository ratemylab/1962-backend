from __future__ import annotations

from pydantic import Field

from app.schema.base import AppSchema, TimestampedSchema


class AnimalBase(AppSchema):
    animal_name: str = Field(..., min_length=1, max_length=50)
    breed_name: str | None = Field(default=None, max_length=100)


class AnimalRead(AnimalBase, TimestampedSchema):
    id: str
    ticket_id: str
