from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)

ReminderStatus = Literal["pending", "completed", "cancelled"]
ReminderDueGroup = Literal["overdue", "today", "upcoming", "later"] | None


def reminder_due_group(
    due_on: date, status: str, today: date | None = None
) -> ReminderDueGroup:
    if status != "pending":
        return None
    local_today = today or datetime.now(ZoneInfo("Asia/Shanghai")).date()
    if due_on < local_today:
        return "overdue"
    if due_on == local_today:
        return "today"
    if due_on <= local_today + timedelta(days=7):
        return "upcoming"
    return "later"


class ReminderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pet_id: UUID | None = None
    title: str = Field(min_length=1, max_length=120)
    due_on: date
    source_record_id: UUID | None = None

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ReminderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pet_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    due_on: date | None = None
    source_record_id: UUID | None = None
    status: ReminderStatus | None = None

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_patch(self) -> "ReminderUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title cannot be null")
        if "due_on" in self.model_fields_set and self.due_on is None:
            raise ValueError("due_on cannot be null")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pet_id: UUID | None
    title: str
    due_on: date
    status: ReminderStatus
    source_record_id: UUID | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def due_group(self) -> ReminderDueGroup:
        return reminder_due_group(self.due_on, self.status)

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_serializer("created_at", "updated_at")
    def serialize_utc(self, value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")
