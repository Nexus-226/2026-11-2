"""LLM Provider 抽象（A 负责）。

P0-4 先用 MockProvider 开发；接入真实模型时实现同一接口即可。
接口不依赖某一家供应商，连接和错误边界与 B 对齐。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.agent.registry import Tool
from app.agent.schemas import ChatHistoryMessage, ToolCallRequest, ToolResult


@dataclass
class ProviderTurn:
    """Provider 的一次输出：要么要调用工具，要么给出最终回复。"""

    tool_call: ToolCallRequest | None = None
    reply: str | None = None


class LLMProvider(Protocol):
    """把对话上下文交给模型，返回下一步（工具调用或最终回复）。"""

    def next_turn(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[Tool],
        tool_results: list[ToolResult],
        history: list[ChatHistoryMessage] | None = None,
    ) -> ProviderTurn:
        """返回下一步；``history`` 只在首轮用于重建上下文，后续轮次忽略。"""
        ...
