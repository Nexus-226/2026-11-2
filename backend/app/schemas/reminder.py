"""站内提醒读取 Schema（P1-1 冻结契约，A 工具与 B Service 共用）。

提醒表示“计划发生”；``due_group`` 是 B 的 Service 按 Asia/Shanghai 当前日
统一计算的派生字段，Agent 不得自行重算。完成/取消项的 ``due_group`` 为 null。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pet_id: UUID | None
    title: str
    due_on: date
    status: Literal["pending", "completed", "cancelled"]
    due_group: Literal["overdue", "today", "upcoming", "later"] | None
    source_record_id: UUID | None
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
