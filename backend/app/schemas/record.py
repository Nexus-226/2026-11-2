from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

RecordType = Literal["vaccine", "deworming", "bath", "weight"]


def _validate_occurred_on(value: date) -> date:
    if value > datetime.now(ZoneInfo("Asia/Shanghai")).date():
        raise ValueError("occurred_on cannot be in the future")
    return value


def _validate_weight(record_type: str, weight_kg: Decimal | None) -> None:
    if record_type == "weight":
        if weight_kg is None:
            raise ValueError("weight_kg is required for weight records")
    elif weight_kg is not None:
        raise ValueError("weight_kg must be null for non-weight records")


class RecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pet_id: UUID | None = None
    record_type: RecordType
    occurred_on: date
    name: str | None = Field(default=None, max_length=100)
    weight_kg: Decimal | None = Field(
        default=None, gt=0, le=500, max_digits=5, decimal_places=2
    )
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("occurred_on")
    @classmethod
    def validate_occurred_on(cls, value: date) -> date:
        return _validate_occurred_on(value)

    @model_validator(mode="after")
    def validate_weight_for_type(self) -> "RecordCreate":
        _validate_weight(self.record_type, self.weight_kg)
        return self


class RecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pet_id: UUID | None = None
    record_type: RecordType | None = None
    occurred_on: date | None = None
    name: str | None = Field(default=None, max_length=100)
    weight_kg: Decimal | None = Field(
        default=None, gt=0, le=500, max_digits=5, decimal_places=2
    )
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("occurred_on")
    @classmethod
    def validate_occurred_on(cls, value: date | None) -> date | None:
        return _validate_occurred_on(value) if value is not None else None

    @model_validator(mode="after")
    def validate_patch(self) -> "RecordUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        if "record_type" in self.model_fields_set and self.record_type is None:
            raise ValueError("record_type cannot be null")
        if "occurred_on" in self.model_fields_set and self.occurred_on is None:
            raise ValueError("occurred_on cannot be null")
        return self


class RecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pet_id: UUID | None
    record_type: RecordType
    occurred_on: date
    name: str | None
    weight_kg: Decimal | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("weight_kg")
    def serialize_weight(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_serializer("created_at", "updated_at")
    def serialize_utc(self, value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")
