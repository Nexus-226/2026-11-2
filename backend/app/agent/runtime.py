"""Agent 工具调用循环（A 负责）。

工具在调用方线程内同步执行，不放入线程池——B 的 PetService 持有请求级
SQLAlchemy Session，跨线程使用不安全。P0 工具都是本地快速调用，无需异步超时；
真实外部工具接入时再按需补超时机制。
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import ValidationError

from app.agent.errors import DomainError, ToolNotFoundError
from app.agent.registry import ToolRegistry
from app.agent.schemas import ToolCallRequest, ToolResult

MAX_TOOL_CALLS_PER_TURN = 3


class AgentRuntime:
    """校验参数并在当前线程同步执行工具调用。"""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        max_tool_calls: int = MAX_TOOL_CALLS_PER_TURN,
    ) -> None:
        self.registry = registry
        self.max_tool_calls = max_tool_calls

    def run_tools(self, calls: Sequence[ToolCallRequest]) -> list[ToolResult]:
        """按顺序执行工具调用，超出 ``max_tool_calls`` 的部分直接丢弃（不执行）。"""
        return [self._execute(call) for call in calls[: self.max_tool_calls]]

    def _execute(self, call: ToolCallRequest) -> ToolResult:
        try:
            tool = self.registry.get(call.name)
        except ToolNotFoundError as exc:
            return ToolResult(
                name=call.name,
                status="error",
                error_code="TOOL_NOT_FOUND",
                message=str(exc),
            )

        try:
            validated = tool.input_schema.model_validate(call.args)
        except ValidationError as exc:
            return ToolResult(
                name=call.name,
                status="error",
                error_code="VALIDATION_ERROR",
                message=str(exc.errors()),
            )

        try:
            data = tool.func(validated)
        except DomainError as exc:
            return ToolResult(
                name=call.name, status="error", error_code=exc.code, message=exc.message
            )
        except Exception as exc:  # noqa: BLE001 - 工具异常统一映射为 INTERNAL_ERROR
            return ToolResult(
                name=call.name,
                status="error",
                error_code="INTERNAL_ERROR",
                message=str(exc),
            )

        return ToolResult(name=call.name, status="success", data=data)
