"""工具注册协议（A 定义）。

Agent 只能调用已注册的工具；每个工具声明输入 Schema，调用前由 Runtime 校验参数。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.agent.errors import ToolNotFoundError


@dataclass(frozen=True)
class Tool:
    """一个可被 Agent 调用的工具。"""

    name: str
    description: str
    input_schema: type[BaseModel]
    func: Callable[[BaseModel], Any]


class ToolRegistry:
    """按名称注册与查找工具。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具已注册: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError:
            raise ToolNotFoundError(name) from None

    def names(self) -> list[str]:
        return list(self._tools)
