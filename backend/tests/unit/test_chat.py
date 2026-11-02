from datetime import date, datetime, timezone
from uuid import UUID

from app.agent.chat import run_chat
from app.agent.providers.base import ProviderTurn
from app.agent.providers.mock import MockProvider
from app.agent.schemas import ToolCallRequest
from app.schemas.pet import PetRead

PET_ID = UUID("b8f34f24-f5cf-4b5c-8d40-073541725a11")


class FakePetService:
    """测试用的宠物 Service，替代 B 尚未提供的真实实现。"""

    def __init__(self, pets: list[PetRead] | None = None) -> None:
        self._pets = {p.id: p for p in (pets or [])}

    def get_pet(self, pet_id: UUID) -> PetRead | None:
        return self._pets.get(pet_id)

    def list_pets(self) -> list[PetRead]:
        return list(self._pets.values())


def _pet() -> PetRead:
    return PetRead(
        id=PET_ID,
        name="豆豆",
        species="dog",
        breed="金毛",
        birthday=date(2023, 5, 1),
        notes="对鸡肉过敏",
        created_at=datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc),
    )


def test_run_chat_calls_tool_then_replies() -> None:
    provider = MockProvider(
        turns=[
            ProviderTurn(
                tool_call=ToolCallRequest(
                    name="get_pet_profile", args={"pet_id": str(PET_ID)}
                )
            ),
            ProviderTurn(reply="已查到豆豆的资料。"),
        ]
    )
    reply = run_chat(
        "豆豆多大了？", PET_ID, FakePetService([_pet()]), provider=provider
    )
    assert reply.reply == "已查到豆豆的资料。"
    assert [t.name for t in reply.tool_calls] == ["get_pet_profile"]
    assert reply.tool_calls[0].status == "success"


def test_run_chat_not_found_is_error() -> None:
    provider = MockProvider(
        turns=[
            ProviderTurn(
                tool_call=ToolCallRequest(
                    name="get_pet_profile", args={"pet_id": str(PET_ID)}
                )
            ),
            ProviderTurn(reply="未找到该宠物。"),
        ]
    )
    reply = run_chat("豆豆多大了？", PET_ID, FakePetService([]), provider=provider)
    assert reply.reply == "未找到该宠物。"
    assert reply.tool_calls[0].status == "error"


def test_run_chat_direct_reply_no_tool() -> None:
    provider = MockProvider(turns=[ProviderTurn(reply="你好！")])
    reply = run_chat("你好", None, FakePetService([]), provider=provider)
    assert reply.reply == "你好！"
    assert reply.tool_calls == []
