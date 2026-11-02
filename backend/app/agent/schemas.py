"""Agent 工具输入/输出 Schema（A 定义）。

``Pet`` 结构与 docs/API.md「P0：宠物资料」草案一致，仅用于工具层类型约束；
P0-2 落地后由 B 在 ``app/schemas/`` 提供权威定义，届时工具输出改为引用 B 的
Schema，避免两处重复。当前属开发期占位，不代表业务字段已冻结。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Pet(BaseModel):
    """宠物资料（字段与 API.md 草案对齐，供工具输出使用）。"""

    id: UUID
    name: str
    species: Literal["dog", "cat", "other"]
    breed: str | None = None
    birthday: date | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class GetPetProfileInput(BaseModel):
    """``get_pet_profile`` 入参。"""

    pet_id: UUID


class ListPetsInput(BaseModel):
    """``list_pets`` 入参（空对象）。"""


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
