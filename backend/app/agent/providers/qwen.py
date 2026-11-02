"""Qwen（DashScope OpenAI 兼容）Provider。

通过 OpenAI 兼容接口调用 qwen-plus，支持 function calling；有状态地维护多轮
工具调用对话。真实密钥从环境变量读取，不提交。
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel

from app.agent.errors import ProviderError
from app.agent.providers.base import ProviderTurn
from app.agent.registry import Tool
from app.agent.schemas import ToolCallRequest, ToolResult


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    return value


def _serialize_result(result: ToolResult) -> str:
    if result.status == "error":
        payload: dict[str, Any] = {
            "error": result.error_code,
            "message": result.message,
        }
    else:
        payload = {"result": _to_jsonable(result.data)}
    return json.dumps(payload, ensure_ascii=False)


class QwenProvider:
    """OpenAI 兼容的 Qwen Provider；有状态地维护 function-calling 对话。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str = "qwen-plus",
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._messages: list[dict[str, Any]] = []
        self._pending_tool_call_id: str | None = None

    def next_turn(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[Tool],
        tool_results: list[ToolResult],
    ) -> ProviderTurn:
        if not self._messages:
            self._messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
        else:
            result = tool_results[-1]
            self._messages.append(
                {
                    "role": "tool",
                    "tool_call_id": self._pending_tool_call_id,
                    "content": _serialize_result(result),
                }
            )

        tools_payload = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema.model_json_schema(),
                },
            }
            for tool in tools
        ]

        message = self._request(tools_payload)
        tool_calls = message.get("tool_calls")
        if tool_calls:
            self._messages.append(
                {"role": "assistant", "content": None, "tool_calls": tool_calls}
            )
            call = tool_calls[0]
            self._pending_tool_call_id = call["id"]
            function = call["function"]
            try:
                args = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            return ProviderTurn(
                tool_call=ToolCallRequest(name=function["name"], args=args)
            )

        content = message.get("content") or ""
        self._messages.append({"role": "assistant", "content": content})
        return ProviderTurn(reply=content)

    def _request(self, tools_payload: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": self._messages,
                    "tools": tools_payload,
                    "tool_choice": "auto",
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]
        except httpx.TimeoutException as exc:
            raise ProviderError("UPSTREAM_TIMEOUT", "模型响应超时") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError("UPSTREAM_ERROR", "模型服务不可用") from exc
        except httpx.RequestError as exc:
            raise ProviderError("SERVICE_UNAVAILABLE", "无法连接模型服务") from exc
