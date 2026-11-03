"""Agent 工具集合（A 定义工具协议，B 提供 Service）。"""

from app.agent.registry import ToolRegistry
from app.agent.service_protocol import PetService, RecordService, ReminderService
from app.agent.tools.pets import make_pet_tools
from app.agent.tools.records import make_record_tools
from app.agent.tools.reminders import make_reminder_tools

__all__ = [
    "build_default_registry",
    "make_pet_tools",
    "make_record_tools",
    "make_reminder_tools",
]


def build_default_registry(
    service: PetService,
    *,
    record_service: RecordService | None = None,
    reminder_service: ReminderService | None = None,
) -> ToolRegistry:
    """注册宠物资料工具，以及（若提供 Service）P1 记录/提醒只读工具。

    record_service / reminder_service 暂缺时工具不注册，便于 A 并行开发、
    B 在 P1-2/P1-4 提供真实实现后再接入。
    """
    registry = ToolRegistry()
    for tool in make_pet_tools(service):
        registry.register(tool)
    if record_service is not None:
        for tool in make_record_tools(record_service):
            registry.register(tool)
    if reminder_service is not None:
        for tool in make_reminder_tools(reminder_service):
            registry.register(tool)
    return registry
