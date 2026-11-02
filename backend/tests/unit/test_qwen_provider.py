import json

import httpx
import pytest

from app.agent.errors import ProviderError
from app.agent.providers.qwen import QwenProvider
from app.agent.registry import Tool
from app.agent.schemas import GetPetProfileInput, ToolResult

PET_ID = "b8f34f24-f5cf-4b5c-8d40-073541725a11"


def _get_pet_profile_tool() -> Tool:
    return Tool(
        name="get_pet_profile",
        description="按 pet_id 读取单个宠物资料。",
        input_schema=GetPetProfileInput,
        func=lambda inp: None,
    )


def _tool_call_response() -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "get_pet_profile",
                                "arguments": json.dumps({"pet_id": PET_ID}),
                            },
                        }
                    ],
                }
            }
        ]
    }


def _reply_response(content: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def test_qwen_provider_tool_call_then_reply() -> None:
    responses = [_tool_call_response(), _reply_response("已查到豆豆的资料。")]
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=responses.pop(0))
    )
    provider = QwenProvider(
        api_key="test-key",
        base_url="https://example.com/compatible-mode/v1",
        model="qwen-plus",
        transport=transport,
    )
    tools = [_get_pet_profile_tool()]

    turn1 = provider.next_turn(
        system_prompt="你是宠物助手。",
        user_message="豆豆多大了？",
        tools=tools,
        tool_results=[],
    )
    assert turn1.reply is None
    assert turn1.tool_call is not None
    assert turn1.tool_call.name == "get_pet_profile"
    assert turn1.tool_call.args == {"pet_id": PET_ID}

    result = ToolResult(name="get_pet_profile", status="success", data={"name": "豆豆"})
    turn2 = provider.next_turn(
        system_prompt="你是宠物助手。",
        user_message="豆豆多大了？",
        tools=tools,
        tool_results=[result],
    )
    assert turn2.reply == "已查到豆豆的资料。"
    assert turn2.tool_call is None


def test_qwen_provider_maps_http_error_to_provider_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(500, json={"error": "boom"})
    )
    provider = QwenProvider(
        api_key="test-key",
        base_url="https://example.com/compatible-mode/v1",
        transport=transport,
    )
    with pytest.raises(ProviderError) as exc_info:
        provider.next_turn(
            system_prompt="sys",
            user_message="hi",
            tools=[],
            tool_results=[],
        )
    assert exc_info.value.code == "UPSTREAM_ERROR"


def test_qwen_provider_maps_bad_json_to_provider_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"not-json")
    )
    provider = QwenProvider(
        api_key="test-key",
        base_url="https://example.com/compatible-mode/v1",
        transport=transport,
    )
    with pytest.raises(ProviderError) as exc_info:
        provider.next_turn(
            system_prompt="sys",
            user_message="hi",
            tools=[],
            tool_results=[],
        )
    assert exc_info.value.code == "UPSTREAM_ERROR"


def test_qwen_provider_maps_malformed_tool_call_to_provider_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{"id": "call_1"}],
                        }
                    }
                ]
            },
        )
    )
    provider = QwenProvider(
        api_key="test-key",
        base_url="https://example.com/compatible-mode/v1",
        transport=transport,
    )
    with pytest.raises(ProviderError) as exc_info:
        provider.next_turn(
            system_prompt="sys",
            user_message="hi",
            tools=[_get_pet_profile_tool()],
            tool_results=[],
        )
    assert exc_info.value.code == "UPSTREAM_ERROR"


def test_qwen_provider_handles_parallel_tool_calls() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_pet_profile",
                                        "arguments": json.dumps({"pet_id": PET_ID}),
                                    },
                                },
                                {
                                    "id": "call_2",
                                    "type": "function",
                                    "function": {
                                        "name": "list_pets",
                                        "arguments": "{}",
                                    },
                                },
                            ],
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    provider = QwenProvider(
        api_key="test-key",
        base_url="https://example.com/compatible-mode/v1",
        transport=transport,
    )
    turn = provider.next_turn(
        system_prompt="sys",
        user_message="hi",
        tools=[_get_pet_profile_tool()],
        tool_results=[],
    )

    assert turn.tool_call is not None
    assert turn.tool_call.name == "get_pet_profile"
    assert requests[0]["parallel_tool_calls"] is False
    assert len(provider._messages[-1]["tool_calls"]) == 1
    assert provider._messages[-1]["tool_calls"][0]["id"] == "call_1"


def test_qwen_provider_maps_non_object_arguments_to_provider_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_pet_profile",
                                        "arguments": "[1, 2, 3]",
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )
    )
    provider = QwenProvider(
        api_key="test-key",
        base_url="https://example.com/compatible-mode/v1",
        transport=transport,
    )
    with pytest.raises(ProviderError) as exc_info:
        provider.next_turn(
            system_prompt="sys",
            user_message="hi",
            tools=[_get_pet_profile_tool()],
            tool_results=[],
        )
    assert exc_info.value.code == "UPSTREAM_ERROR"


def test_qwen_provider_maps_non_dict_message_to_provider_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"choices": [{"message": "not-a-dict"}]},
        )
    )
    provider = QwenProvider(
        api_key="test-key",
        base_url="https://example.com/compatible-mode/v1",
        transport=transport,
    )
    with pytest.raises(ProviderError) as exc_info:
        provider.next_turn(
            system_prompt="sys",
            user_message="hi",
            tools=[],
            tool_results=[],
        )
    assert exc_info.value.code == "UPSTREAM_ERROR"
