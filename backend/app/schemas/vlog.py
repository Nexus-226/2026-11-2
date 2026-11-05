from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.schemas.record import _validate_occurred_on

# P2 提案（PR #92）：首版每篇选传最多 3 张 JPEG/PNG（每张 5 MB）或 1 段兼容
# 浏览器的 MP4（20 MB）；数值为工作量估算用的默认值。
MAX_IMAGES_PER_VLOG = 3
MAX_VIDEOS_PER_VLOG = 1
IMAGE_MAX_BYTES = 5 * 1024 * 1024
VIDEO_MAX_BYTES = 20 * 1024 * 1024

MediaType = Literal["image", "video"]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _serialize_utc(value: datetime) -> str:
    return _ensure_utc(value).isoformat().replace("+00:00", "Z")


class VlogCreate(BaseModel):
    """POST /api/v1/vlogs 的 multipart 表单字段。"""

    model_config = ConfigDict(extra="forbid")

    pet_id: UUID
    occurred_on: date
    caption: str | None = Field(default=None, max_length=2000)

    @field_validator("caption")
    @classmethod
    def normalize_caption(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("occurred_on")
    @classmethod
    def validate_occurred_on(cls, value: date) -> date:
        return _validate_occurred_on(value)


class VlogUpdate(BaseModel):
    """PATCH /api/v1/vlogs/{id}（JSON）；首版不支持替换媒体，删除后重建。"""

    model_config = ConfigDict(extra="forbid")

    caption: str | None = Field(default=None, max_length=2000)
    occurred_on: date | None = None

    @field_validator("caption")
    @classmethod
    def normalize_caption(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("occurred_on")
    @classmethod
    def validate_occurred_on(cls, value: date | None) -> date | None:
        if value is None:
            return None
        return _validate_occurred_on(value)

    @model_validator(mode="after")
    def validate_patch(self) -> "VlogUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        if "occurred_on" in self.model_fields_set and self.occurred_on is None:
            raise ValueError("occurred_on cannot be null")
        return self


class VlogMediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    media_type: MediaType
    filename: str
    content_type: str
    size_bytes: int
    url: str
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value)

    @field_serializer("created_at")
    def serialize_utc(self, value: datetime) -> str:
        return _serialize_utc(value)


class VlogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pet_id: UUID
    caption: str | None
    occurred_on: date
    media: list[VlogMediaRead]
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value)

    @field_serializer("created_at", "updated_at")
    def serialize_utc(self, value: datetime) -> str:
        return _serialize_utc(value)
