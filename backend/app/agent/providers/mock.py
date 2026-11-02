"""Mock Provider（测试用，不依赖真实 LLM）。

按构造时传入的脚本依次返回工具调用或最终回复；脚本用完后返回兜底回复。
"""

from __future__ import annotations

from app.agent.providers.base import ProviderTurn
from app.agent.schemas import ToolResult


class MockProvider:
    def __init__(self, turns: list[ProviderTurn] | None = None) -> None:
        self._turns = list(turns or [])
        self._index = 0

    def next_turn(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tool_descriptions: str,
        tool_results: list[ToolResult],
    ) -> ProviderTurn:
        if self._index < len(self._turns):
            turn = self._turns[self._index]
            self._index += 1
            return turn
        return ProviderTurn(reply="（mock）抱歉，我暂时无法回答。")
