"""Agent 工具集合（A 定义工具协议，B 提供 Service）。"""

from uuid import UUID

from app.agent.registry import ToolRegistry
from app.agent.service_protocol import (
    NearbyService,
    PetService,
    RecordService,
    ReminderService,
)
from app.agent.tools.nearby import make_nearby_tools
from app.agent.tools.pets import make_pet_tools
from app.agent.tools.records import make_record_draft_tool, make_record_tools
from app.agent.tools.reminders import make_reminder_tools

__all__ = [
    "build_default_registry",
    "make_nearby_tools",
    "make_pet_tools",
    "make_record_draft_tool",
    "make_record_tools",
    "make_reminder_tools",
]


def build_default_registry(
    service: PetService,
    *,
    record_service: RecordService | None = None,
    reminder_service: ReminderService | None = None,
    nearby_service: NearbyService | None = None,
    current_pet_id: UUID | None = None,
) -> ToolRegistry:
    """注册宠物资料工具，以及（若提供 Service）P1 只读工具。

    ``current_pet_id`` 绑定到记录/提醒工具，工具据此约束宠物范围；附近搜索按坐标
    查询、不绑定宠物。record_service / reminder_service / nearby_service 暂缺时
    对应工具不注册，便于 A 并行开发、B 提供真实实现后再接入。
    """
    registry = ToolRegistry()
    for tool in make_pet_tools(service):
        registry.register(tool)
    # P2 草稿工具不依赖任何 Service（只读、不写入），始终注册。
    registry.register(make_record_draft_tool())
    if record_service is not None:
        for tool in make_record_tools(record_service, current_pet_id):
            registry.register(tool)
    if reminder_service is not None:
        for tool in make_reminder_tools(reminder_service, current_pet_id):
            registry.register(tool)
    if nearby_service is not None:
        for tool in make_nearby_tools(nearby_service):
            registry.register(tool)
    return registry
