"""A 对 B 的 Service 依赖声明（A 定义协议，B 提供实现）。

工具只通过 Service 取数，不直接访问数据库；P0-3 开发期用测试中的 FakePetService，
真实联调时替换为 B 的 ``app/services`` 实现。
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.schemas.pet import PetRead


class PetService(Protocol):
    """宠物资料服务（B 负责实现）。"""

    def get_pet(self, pet_id: UUID) -> PetRead | None:
        """按 id 返回宠物，不存在返回 None。"""
        ...

    def list_pets(self) -> list[PetRead]:
        """返回全部宠物，无结果返回 []。"""
        ...
