"""Agent 工具调用循环（A 负责）。

P0-3：直接按给定工具调用请求执行，强制「每轮最多连续 3 次」与单次超时；
P0-4 由 LLM Provider 产生 ToolCallRequest 列表并驱动本循环。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agent.errors import DomainError, ToolNotFoundError, ToolTimeout
from app.agent.registry import ToolRegistry
from app.agent.schemas import ToolCallRequest, ToolResult

MAX_TOOL_CALLS_PER_TURN = 3
DEFAULT_TOOL_TIMEOUT_SECONDS = 30.0


class AgentRuntime:
    """校验参数并按注册表执行工具调用。"""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        max_tool_calls: int = MAX_TOOL_CALLS_PER_TURN,
        tool_timeout_seconds: float | None = DEFAULT_TOOL_TIMEOUT_SECONDS,
    ) -> None:
        self.registry = registry
        self.max_tool_calls = max_tool_calls
        self.tool_timeout_seconds = tool_timeout_seconds

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
            data = self._call_with_timeout(tool.func, validated)
        except DomainError as exc:
            return ToolResult(
                name=call.name, status="error", error_code=exc.code, message=exc.message
            )
        except ToolTimeout:
            return ToolResult(
                name=call.name,
                status="error",
                error_code="UPSTREAM_TIMEOUT",
                message="工具调用超时",
            )
        except Exception as exc:  # noqa: BLE001 - 工具异常统一映射为 INTERNAL_ERROR
            return ToolResult(
                name=call.name,
                status="error",
                error_code="INTERNAL_ERROR",
                message=str(exc),
            )

        return ToolResult(name=call.name, status="success", data=data)

    def _call_with_timeout(
        self, func: Callable[[BaseModel], Any], validated: BaseModel
    ) -> Any:
        if self.tool_timeout_seconds is None:
            return func(validated)
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            future = pool.submit(func, validated)
            try:
                return future.result(timeout=self.tool_timeout_seconds)
            except FuturesTimeoutError:
                future.cancel()
                raise ToolTimeout from None
        finally:
            # wait=False：超时后不阻塞等待仍在运行的线程，保证超时真正限制等待时间。
            pool.shutdown(wait=False, cancel_futures=True)
