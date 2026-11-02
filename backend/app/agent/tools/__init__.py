"""Agent 工具集合（A 定义工具协议，B 提供 Service）。"""

from app.agent.registry import ToolRegistry
from app.agent.service_protocol import PetService
from app.agent.tools.pets import make_pet_tools

__all__ = ["build_default_registry", "make_pet_tools"]


def build_default_registry(service: PetService) -> ToolRegistry:
    """注册 P0 宠物资料工具，返回可直接交给 AgentRuntime 的注册表。"""
    registry = ToolRegistry()
    for tool in make_pet_tools(service):
        registry.register(tool)
    return registry
