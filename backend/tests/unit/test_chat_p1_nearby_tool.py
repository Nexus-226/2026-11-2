"""P1-11 附近搜索工具的聊天链路验证（Mock Provider + 模拟 Service）。

工具层边界由 test_agent_p1_nearby_tools.py 覆盖；这里验证 nearby 工具经 run_chat
编排后能被调用、返回数据。
"""

from uuid import UUID

from app.agent.chat import run_chat
from app.agent.providers.base import ProviderTurn
from app.agent.providers.mock import MockProvider
from app.agent.schemas import ToolCallRequest, ToolResult
from app.schemas.nearby import GeoLocation, NearbyResponse, SearchCenter
from app.schemas.pet import PetRead


class FakePetService:
    def get_pet(self, pet_id: UUID) -> PetRead | None:
        return None

    def list_pets(self) -> list[PetRead]:
        return []


class FakeNearbyService:
    def search_nearby(self, **kwargs: object) -> NearbyResponse:
        return NearbyResponse(
            places=[],
            search_center=SearchCenter(
                location=GeoLocation(lat=39.9001, lng=116.4001),
                source="user_location",
                label="当前位置",
            ),
            source="demo",
            fallback_reason="amap_not_configured",
        )


def test_run_chat_uses_nearby_tool() -> None:
    provider = MockProvider(
        turns=[
            ProviderTurn(
                tool_call=ToolCallRequest(
                    name="search_nearby_pet_services",
                    args={"lat": 39.9001, "lng": 116.4001, "type": "pet_hospital"},
                )
            ),
            ProviderTurn(reply="附近暂时没有演示地点。"),
        ]
    )
    reply = run_chat(
        "附近有哪些宠物医院？",
        None,
        FakePetService(),
        nearby_service=FakeNearbyService(),
        provider=provider,
    )
    assert reply.reply == "附近暂时没有演示地点。"
    assert [t.name for t in reply.tool_calls] == ["search_nearby_pet_services"]
    assert reply.tool_calls[0].status == "success"


class CapturingProvider:
    """记录 run_chat 传给 Provider 的工具结果，断言空列表/来源/回退完整透传。"""

    def __init__(self) -> None:
        self.captured_results: list[ToolResult] | None = None

    def next_turn(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[object],
        tool_results: list[ToolResult],
        history: list[object] | None = None,
    ) -> ProviderTurn:
        if tool_results:
            self.captured_results = tool_results
            return ProviderTurn(reply="实时服务未接入，当前为演示数据。")
        return ProviderTurn(
            tool_call=ToolCallRequest(
                name="search_nearby_pet_services",
                args={"lat": 39.9001, "lng": 116.4001, "type": "pet_hospital"},
            )
        )


def test_run_chat_passes_full_demo_response_to_provider() -> None:
    provider = CapturingProvider()
    reply = run_chat(
        "附近有哪些宠物医院？",
        None,
        FakePetService(),
        nearby_service=FakeNearbyService(),
        provider=provider,
    )
    assert provider.captured_results is not None
    result = provider.captured_results[0]
    assert result.status == "success"
    assert result.data.places == []
    assert result.data.source == "demo"
    assert result.data.fallback_reason == "amap_not_configured"
    assert reply.tool_calls[0].status == "success"
