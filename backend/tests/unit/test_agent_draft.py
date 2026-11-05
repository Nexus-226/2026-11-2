"""P2 洗澡记录草稿：Agent 只生成结构化草稿，不写入；run_chat 捕获为 ChatReply.draft。"""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.agent.chat import run_chat
from app.agent.providers.base import ProviderTurn
from app.agent.providers.mock import MockProvider
from app.agent.schemas import RecordDraft, ToolCallRequest
from app.schemas.pet import PetRead

PET_ID = UUID("b8f34f24-f5cf-4b5c-8d40-073541725a11")


class FakePetService:
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
        other_species=None,
        breed="金毛",
        birthday=date(2023, 5, 1),
        notes="对鸡肉过敏",
        created_at=datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc),
    )


def test_run_chat_captures_bath_record_draft() -> None:
    provider = MockProvider(
        turns=[
            ProviderTurn(
                tool_call=ToolCallRequest(
                    name="propose_record_draft",
                    args={"occurred_on": "2026-01-01", "pet_id": str(PET_ID)},
                )
            ),
            ProviderTurn(reply="已生成洗澡记录草稿，请核对后保存。"),
        ]
    )
    reply = run_chat(
        "帮我记一下豆豆昨天洗澡了", PET_ID, FakePetService([_pet()]), provider=provider
    )
    assert reply.reply == "已生成洗澡记录草稿，请核对后保存。"
    assert reply.draft is not None
    assert reply.draft.record_type == "bath"
    assert reply.draft.occurred_on == date(2026, 1, 1)
    assert reply.draft.pet_id == PET_ID
    assert reply.draft.name is None
    assert reply.draft.notes is None
    assert [t.name for t in reply.tool_calls] == ["propose_record_draft"]
    assert reply.tool_calls[0].status == "success"


def test_run_chat_no_draft_when_model_replies_without_tool() -> None:
    provider = MockProvider(turns=[ProviderTurn(reply="豆豆最近洗过澡了吗？")])
    reply = run_chat(
        "豆豆最近洗过澡了吗？", PET_ID, FakePetService([_pet()]), provider=provider
    )
    assert reply.draft is None
    assert reply.tool_calls == []


def test_run_chat_rejects_future_draft_date() -> None:
    future = (
        datetime.now(ZoneInfo("Asia/Shanghai")).date() + timedelta(days=1)
    ).isoformat()
    provider = MockProvider(
        turns=[
            ProviderTurn(
                tool_call=ToolCallRequest(
                    name="propose_record_draft",
                    args={"occurred_on": future, "pet_id": str(PET_ID)},
                )
            ),
            ProviderTurn(reply="请提供过去的日期。"),
        ]
    )
    reply = run_chat(
        "帮我记一下豆豆明天洗澡了", PET_ID, FakePetService([_pet()]), provider=provider
    )
    assert reply.draft is None
    assert reply.tool_calls[0].name == "propose_record_draft"
    assert reply.tool_calls[0].status == "error"


def test_run_chat_rejects_draft_without_pet() -> None:
    provider = MockProvider(
        turns=[
            ProviderTurn(
                tool_call=ToolCallRequest(
                    name="propose_record_draft",
                    args={"occurred_on": "2026-01-01"},
                )
            ),
            ProviderTurn(reply="请先选择宠物。"),
        ]
    )
    reply = run_chat("帮我记一下洗澡", None, FakePetService([]), provider=provider)
    assert reply.draft is None
    assert reply.tool_calls[0].status == "error"


def test_record_draft_rejects_future_date() -> None:
    future = datetime.now(ZoneInfo("Asia/Shanghai")).date() + timedelta(days=1)
    with pytest.raises(ValidationError):
        RecordDraft(occurred_on=future, pet_id=PET_ID)


def test_record_draft_defaults_to_bath_and_strips_name() -> None:
    draft = RecordDraft(
        occurred_on=date(2026, 1, 1), pet_id=PET_ID, name="  香波  ", notes=" 用了香波 "
    )
    assert draft.record_type == "bath"
    assert draft.name == "香波"
    assert draft.notes == " 用了香波 "
