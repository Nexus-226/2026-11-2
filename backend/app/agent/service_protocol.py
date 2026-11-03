"""A 对 B 的 Service 依赖声明（A 定义协议，B 提供实现）。

工具只通过 Service 取数，不直接访问数据库；P0-3 开发期用测试中的 FakePetService，
真实联调时替换为 B 的 ``app/services`` 实现。P1 记录/提醒同理：A 先定义查询协议，
B 在 P1-2/P1-4 提供真实实现，期间 A 用模拟 Service 并行开发。
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Protocol
from uuid import UUID

from app.schemas.nearby import NearbyCategory, NearbyResponse, RequestCenterSource
from app.schemas.pet import PetRead
from app.schemas.record import RecordRead
from app.schemas.reminder import ReminderRead


class PetService(Protocol):
    """宠物资料服务（B 负责实现）。"""

    def get_pet(self, pet_id: UUID) -> PetRead | None:
        """按 id 返回宠物，不存在返回 None。"""
        ...

    def list_pets(self) -> list[PetRead]:
        """返回全部宠物，无结果返回 []。"""
        ...


class RecordService(Protocol):
    """日常记录查询服务（B 负责实现）。"""

    def list_records(
        self,
        *,
        pet_id: UUID | None = None,
        record_type: Literal["vaccine", "deworming", "bath", "weight"] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[RecordRead]:
        """按宠物、类型、时间范围查询记录；无匹配返回 []，失败抛可识别异常。"""
        ...


class ReminderService(Protocol):
    """站内提醒查询服务（B 负责实现）。"""

    def list_reminders(
        self,
        *,
        pet_id: UUID | None = None,
        status: Literal["pending", "completed", "cancelled"] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[ReminderRead]:
        """按宠物、状态、时间范围查询提醒；无匹配返回 []，失败抛可识别异常。"""
        ...


class NearbyService(Protocol):
    """附近服务查询（B 负责实现，P1-8 演示数据版、P1-9 高德接入）。"""

    def search_nearby(
        self,
        *,
        lat: float,
        lng: float,
        category: NearbyCategory,
        radius_m: int,
        center_source: RequestCenterSource,
    ) -> NearbyResponse:
        """按 WGS84 中心、类型、半径查询附近地点。

        ``center_source`` 原样传给附近查询并用于响应 ``search_center.source``；
        无匹配返回 ``NearbyResponse.places == []``，失败抛可识别异常（如
        ``UPSTREAM_ERROR``/``UPSTREAM_TIMEOUT``），不把失败伪装成空结果。
        """
        ...
