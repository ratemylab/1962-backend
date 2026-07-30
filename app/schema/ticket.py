from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schema.base import ContractDateTime


ALPHANUMERIC_PATTERN = re.compile(r"^[A-Za-z0-9]+$")
LETTERS_SPACES_PATTERN = re.compile(r"^[A-Za-z ]+$")
LETTERS_SPACES_DOTS_PATTERN = re.compile(r"^[A-Za-z .]+$")

# Statuses treated as closed/terminal for the conditional closedDateTime rule
# (Update Ticket, contract section 4.3.2). The contract does not enumerate them,
# so a documented set is used.
CLOSED_TICKET_STATUSES = {"CLOSED", "RESOLVED", "TERMINATED", "COMPLETED"}


def _validate_non_blank(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


class ContractSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TicketDetailsCreate(ContractSchema):
    ticket_status: str = Field(..., alias="ticketStatus", min_length=1, max_length=50)
    type: str = Field(..., min_length=1, max_length=50)
    created_date_time: ContractDateTime = Field(..., alias="createdDateTime")

    @field_validator("ticket_status")
    @classmethod
    def validate_ticket_status(cls, value: str) -> str:
        return _validate_non_blank(value, "ticketStatus")

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        return _validate_non_blank(value, "type")

    @field_validator("created_date_time")
    @classmethod
    def validate_created_date_time_not_future(cls, value: datetime) -> datetime:
        if value > datetime.now(timezone.utc):
            raise ValueError("createdDateTime must not be a future timestamp")
        return value


class FarmerDetailsCreate(ContractSchema):
    farmer_id: str = Field(..., alias="farmerId", min_length=1, max_length=20)
    farmer_name: str = Field(..., alias="farmerName", min_length=1, max_length=100)

    @field_validator("farmer_id")
    @classmethod
    def validate_farmer_id(cls, value: str) -> str:
        _validate_non_blank(value, "farmerId")
        if not ALPHANUMERIC_PATTERN.fullmatch(value):
            raise ValueError("farmerId must be alphanumeric")
        return value

    @field_validator("farmer_name")
    @classmethod
    def validate_farmer_name(cls, value: str) -> str:
        _validate_non_blank(value, "farmerName")
        if not LETTERS_SPACES_PATTERN.fullmatch(value):
            raise ValueError("farmerName must contain letters and spaces only")
        return value


class LocationDetailsCreate(ContractSchema):
    village_id: int = Field(..., alias="villageId", gt=0)
    village: str = Field(..., min_length=1, max_length=100)
    panchayat_id: int = Field(..., alias="panchayatId", gt=0)
    panchayat: str = Field(..., min_length=1, max_length=100)
    block_id: int = Field(..., alias="blockId", gt=0)
    block: str = Field(..., min_length=1, max_length=100)
    district: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)

    @field_validator("village", "panchayat", "block", "district", "state")
    @classmethod
    def validate_location_text(cls, value: str) -> str:
        return _validate_non_blank(value, "location field")


class AnimalCreate(ContractSchema):
    animal_name: str = Field(..., alias="animalName", min_length=1, max_length=50)
    breed_name: str | None = Field(default=None, alias="breedName", max_length=100)

    @field_validator("animal_name")
    @classmethod
    def validate_animal_name(cls, value: str) -> str:
        return _validate_non_blank(value, "animalName")


class DiseaseTreatmentDetailsCreate(ContractSchema):
    disease: str = Field(..., min_length=1, max_length=200)
    symptoms: list[str] = Field(..., min_length=1)

    @field_validator("disease")
    @classmethod
    def validate_disease(cls, value: str) -> str:
        return _validate_non_blank(value, "disease")

    @field_validator("symptoms")
    @classmethod
    def validate_symptoms(cls, value: list[str]) -> list[str]:
        for symptom in value:
            if not symptom or not symptom.strip():
                raise ValueError("symptoms must contain non-empty strings")
            if len(symptom) > 200:
                raise ValueError("each symptom must be at most 200 characters")
        return value


class TicketCreateRequest(ContractSchema):
    ticket_id: str = Field(..., alias="ticketId", min_length=1, max_length=50)
    ticket_details: TicketDetailsCreate = Field(..., alias="ticketDetails")
    farmer_details: FarmerDetailsCreate = Field(..., alias="farmerDetails")
    location_details: LocationDetailsCreate = Field(..., alias="locationDetails")
    animals: list[AnimalCreate] = Field(..., min_length=1)
    disease_treatment_details: DiseaseTreatmentDetailsCreate = Field(
        ...,
        alias="diseaseTreatmentDetails",
    )

    @field_validator("ticket_id")
    @classmethod
    def validate_ticket_id(cls, value: str) -> str:
        _validate_non_blank(value, "ticketId")
        if not ALPHANUMERIC_PATTERN.fullmatch(value):
            raise ValueError("ticketId must be alphanumeric")
        return value


class TicketCreateResponse(ContractSchema):
    ticket_id: str = Field(..., alias="ticketId")


class TicketUpdateDetails(ContractSchema):
    ticket_status: str = Field(..., alias="ticketStatus", min_length=1, max_length=50)
    closed_date_time: ContractDateTime | None = Field(default=None, alias="closedDateTime")

    @field_validator("ticket_status")
    @classmethod
    def validate_ticket_status(cls, value: str) -> str:
        return _validate_non_blank(value, "ticketStatus")

    @model_validator(mode="after")
    def validate_closed_date_time_rule(self) -> "TicketUpdateDetails":
        is_terminal = self.ticket_status.strip().upper() in CLOSED_TICKET_STATUSES
        if is_terminal and self.closed_date_time is None:
            raise ValueError(
                "closedDateTime is required when ticketStatus transitions to a closed/terminal state"
            )
        if not is_terminal and self.closed_date_time is not None:
            raise ValueError(
                "closedDateTime must be omitted or null unless ticketStatus is a closed/terminal state"
            )
        return self


class MvuDetailsUpdate(ContractSchema):
    doctor_id: str = Field(..., alias="doctorId", min_length=1, max_length=20)
    doctor_name: str = Field(..., alias="doctorName", min_length=1, max_length=100)
    paravet_id: str = Field(..., alias="paravetId", min_length=1, max_length=20)
    paravet_name: str = Field(..., alias="paravetName", min_length=1, max_length=100)
    mvu_number: str = Field(..., alias="mvuNumber", min_length=1, max_length=20)

    @field_validator("doctor_id")
    @classmethod
    def validate_doctor_id(cls, value: str) -> str:
        return _validate_non_blank(value, "doctorId")

    @field_validator("doctor_name")
    @classmethod
    def validate_doctor_name(cls, value: str) -> str:
        _validate_non_blank(value, "doctorName")
        if not LETTERS_SPACES_DOTS_PATTERN.fullmatch(value):
            raise ValueError("doctorName must contain letters, spaces and dots only")
        return value

    @field_validator("paravet_id")
    @classmethod
    def validate_paravet_id(cls, value: str) -> str:
        return _validate_non_blank(value, "paravetId")

    @field_validator("paravet_name")
    @classmethod
    def validate_paravet_name(cls, value: str) -> str:
        _validate_non_blank(value, "paravetName")
        if not LETTERS_SPACES_DOTS_PATTERN.fullmatch(value):
            raise ValueError("paravetName must contain letters, spaces and dots only")
        return value

    @field_validator("mvu_number")
    @classmethod
    def validate_mvu_number(cls, value: str) -> str:
        return _validate_non_blank(value, "mvuNumber")


class DiseaseTreatmentDetailsUpdate(ContractSchema):
    disease: str = Field(..., min_length=1, max_length=200)
    symptoms: list[str] | None = Field(default=None)
    treatment_given: str | None = Field(default=None, alias="treatmentGiven")

    @field_validator("disease")
    @classmethod
    def validate_disease(cls, value: str) -> str:
        return _validate_non_blank(value, "disease")

    @field_validator("symptoms")
    @classmethod
    def validate_symptoms(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        for symptom in value:
            if len(symptom) > 200:
                raise ValueError("each symptom must be at most 200 characters")
        return value


class TicketUpdateRequest(ContractSchema):
    ticket_id: str = Field(..., alias="ticketId", min_length=1, max_length=50)
    ticket_details: TicketUpdateDetails = Field(..., alias="ticketDetails")
    mvu_details: MvuDetailsUpdate = Field(..., alias="mvuDetails")
    disease_treatment_details: DiseaseTreatmentDetailsUpdate = Field(
        ...,
        alias="diseaseTreatmentDetails",
    )

    @field_validator("ticket_id")
    @classmethod
    def validate_ticket_id(cls, value: str) -> str:
        _validate_non_blank(value, "ticketId")
        if not ALPHANUMERIC_PATTERN.fullmatch(value):
            raise ValueError("ticketId must be alphanumeric")
        return value


class TicketUpdateResponse(ContractSchema):
    ticket_id: str = Field(..., alias="ticketId")
