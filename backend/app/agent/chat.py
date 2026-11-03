"""Agent 对话编排（A 负责）。

``run_chat`` 是给 B 的 ``/api/v1/chat`` 路由调用的入口：B 传入 message、pet_id、
绑定好 DB session 的 PetService，以及按会话读取的历史消息；这里驱动 LLM Provider
→ 工具调用 → 结果回填 → 最终回复，返回 reply 和 tool_calls。session_id /
message_id / 历史持久化由 B 负责。
"""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.providers.base import LLMProvider
from app.agent.providers.factory import build_default_provider
from app.agent.runtime import MAX_TOOL_CALLS_PER_TURN, AgentRuntime
from app.agent.schemas import ChatHistoryMessage, ToolResult
from app.agent.service_protocol import PetService
from app.agent.tools import build_default_registry

# 最近 10 个完整轮次（20 条消息）；字符数只是保守预算，给系统提示、本次问题、
# 工具定义、当前工具结果和输出预留空间，不视为精确 token 计数。
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CHARS = 8000


class ToolCallSummary(BaseModel):
    """chat 响应里的 tool_calls 项：只暴露名称和状态，不泄露参数/结果。"""

    name: str
    status: Literal["success", "error"]


class ChatReply(BaseModel):
    """run_chat 返回的内容；session_id / message_id 由 B 补充。"""

    reply: str
    tool_calls: list[ToolCallSummary] = Field(default_factory=list)


def _select_history(
    history: list[ChatHistoryMessage] | None,
) -> list[ChatHistoryMessage]:
    """取最近若干完整轮次，并限制总字符数；不保留半轮消息。"""
    messages = [item for item in history or [] if item.content.strip()]
    if not messages:
        return []

    messages = messages[-MAX_HISTORY_MESSAGES:]

    selected: list[ChatHistoryMessage] = []
    total_chars = 0
    for item in reversed(messages):
        if selected and total_chars + len(item.content) > MAX_HISTORY_CHARS:
            break
        selected.append(item)
        total_chars += len(item.content)
    selected.reverse()

    # 只保留完整轮次：去掉开头孤立的 assistant 和结尾没有回复的 user。
    while selected and selected[0].role == "assistant":
        selected.pop(0)
    while selected and selected[-1].role == "user":
        selected.pop()
    return selected


def run_chat(
    message: str,
    pet_id: UUID | None,
    service: PetService,
    *,
    provider: LLMProvider | None = None,
    max_tool_calls: int = MAX_TOOL_CALLS_PER_TURN,
    history: list[ChatHistoryMessage] | None = None,
) -> ChatReply:
    registry = build_default_registry(service)
    runtime = AgentRuntime(registry, max_tool_calls=max_tool_calls)
    provider = provider or build_default_provider()
    tools = [registry.get(name) for name in registry.names()]
    selected_history = _select_history(history)

    system = SYSTEM_PROMPT + f" 今天是 {date.today().isoformat()}。"
    if pet_id is not None:
        system += f" 当前关联宠物 pet_id={pet_id}。"

    summaries: list[ToolCallSummary] = []
    results: list[ToolResult] = []
    tool_call_count = 0

    while True:
        turn = provider.next_turn(
            system_prompt=system,
            user_message=message,
            tools=tools,
            tool_results=results,
            # 只在首轮拼接历史；同次请求的工具循环继续追加调用与结果。
            history=selected_history if tool_call_count == 0 else None,
        )
        if turn.reply is not None:
            return ChatReply(reply=turn.reply, tool_calls=summaries)
        if turn.tool_call is None:
            return ChatReply(reply="抱歉，我暂时无法回答。", tool_calls=summaries)
        if tool_call_count >= max_tool_calls:
            return ChatReply(
                reply="抱歉，这个问题需要更多信息，我暂时无法回答。",
                tool_calls=summaries,
            )
        result = runtime.run_tools([turn.tool_call])[0]
        tool_call_count += 1
        results.append(result)
        summaries.append(ToolCallSummary(name=result.name, status=result.status))
