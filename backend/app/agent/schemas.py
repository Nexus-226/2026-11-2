"""Agent 工具调用 Schema；宠物资料使用 B 提供的权威 PetRead。"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class GetPetProfileInput(BaseModel):
    """``get_pet_profile`` 入参。"""

    pet_id: UUID


class ListPetsInput(BaseModel):
    """``list_pets`` 入参（空对象）。"""


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
