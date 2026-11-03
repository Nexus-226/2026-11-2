"""Agent 工具调用 Schema；宠物资料使用 B 提供的权威 PetRead。"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class GetPetProfileInput(BaseModel):
    """``get_pet_profile`` 入参。"""

    pet_id: UUID


class ListPetsInput(BaseModel):
    """``list_pets`` 入参（空对象）。"""


class ListPetRecordsInput(BaseModel):
    """``list_pet_records`` 入参；过滤字段均可选。"""

    pet_id: UUID | None = None
    record_type: Literal["vaccine", "deworming", "bath", "weight"] | None = None
    from_date: date | None = None
    to_date: date | None = None

    @model_validator(mode="after")
    def validate_range(self) -> ListPetRecordsInput:
        if (
            self.from_date is not None
            and self.to_date is not None
            and self.from_date > self.to_date
        ):
            raise ValueError("from_date must not be later than to_date")
        return self


class ListPetRemindersInput(BaseModel):
    """``list_pet_reminders`` 入参；过滤字段均可选。"""

    pet_id: UUID | None = None
    status: Literal["pending", "completed", "cancelled"] | None = None
    from_date: date | None = None
    to_date: date | None = None

    @model_validator(mode="after")
    def validate_range(self) -> ListPetRemindersInput:
        if (
            self.from_date is not None
            and self.to_date is not None
            and self.from_date > self.to_date
        ):
            raise ValueError("from_date must not be later than to_date")
        return self


class ChatHistoryMessage(BaseModel):
    """一条历史对话消息（P0-8）；只保留对话语义，不重放工具调用。

    ``pet_id`` 用于识别旧宠物上下文；B 未提供时按 ``None`` 处理，不做跨宠物过滤。
    """

    role: Literal["user", "assistant"]
    content: str
    pet_id: UUID | None = None


class ToolCallRequest(BaseModel):
    """一次工具调用请求（P0-4 由 LLM 产生，P0-3 由 Runtime 直接驱动）。"""

    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """工具执行结果；对外暴露到 chat 响应时只保留 name 和 status，不含 data/参数。"""

    name: str
    status: Literal["success", "error"]
    data: Any | None = None
    error_code: str | None = None
    message: str | None = None
