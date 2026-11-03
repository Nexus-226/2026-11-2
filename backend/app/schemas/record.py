"""日常记录读取 Schema（P1-1 冻结契约，A 工具与 B Service 共用）。

记录表示“已经发生”；字段与 docs/API.md 的 P1-1 提案一致。创建/更新校验由
B 在 P1-2 的 Create/Update Schema 中实现，这里只负责读取结构的类型。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


class RecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pet_id: UUID | None
    record_type: Literal["vaccine", "deworming", "bath", "weight"]
    occurred_on: date
    name: str | None
    weight_kg: float | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_serializer("created_at", "updated_at")
    def serialize_utc(self, value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")
