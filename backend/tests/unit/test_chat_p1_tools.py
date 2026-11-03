"""P1-5 记录/提醒工具的完整聊天链路验证（Mock Provider + 模拟 Service + P0-8 历史）。

工具层的边界（空/失败/校验/隔离）由 test_agent_p1_tools.py 覆盖；这里验证工具
经 run_chat 编排后能真正被调用、返回数据，并与 P0-8 的历史传入一起工作。
"""

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from app.agent.chat import run_chat
from app.agent.errors import DomainError
from app.agent.providers.base import ProviderTurn
from app.agent.providers.mock import MockProvider
from app.agent.schemas import ChatHistoryMessage, ToolCallRequest
from app.schemas.pet import PetRead
from app.schemas.record import RecordRead
from app.schemas.reminder import ReminderRead

PET_ID = UUID("b8f34f24-f5cf-4b5c-8d40-073541725a11")


class FakePetService:
    def get_pet(self, pet_id: UUID) -> PetRead | None:
        return None

    def list_pets(self) -> list[PetRead]:
        return []


class FakeRecordService:
    def __init__(self, records: list[RecordRead] | None = None) -> None:
        self._records = list(records or [])

    def list_records(self, **kwargs: object) -> list[RecordRead]:
        return self._records


class FakeReminderService:
    def __init__(self, reminders: list[ReminderRead] | None = None) -> None:
        self._reminders = list(reminders or [])

    def list_reminders(self, **kwargs: object) -> list[ReminderRead]:
        return self._reminders


class FailingRecordService:
    def list_records(self, **kwargs: object) -> list[RecordRead]:
        raise DomainError("UPSTREAM_ERROR", "记录服务不可用")


def _record(**overrides: object) -> RecordRead:
    base: dict[str, object] = {
        "id": uuid4(),
        "pet_id": PET_ID,
        "record_type": "deworming",
        "occurred_on": date(2026, 10, 20),
        "name": "体内驱虫",
        "weight_kg": None,
        "notes": None,
        "created_at": datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return RecordRead(**base)


def _reminder(**overrides: object) -> ReminderRead:
    base: dict[str, object] = {
        "id": uuid4(),
        "pet_id": PET_ID,
        "title": "下次驱虫",
        "due_on": date(2026, 11, 9),
        "status": "pending",
        "source_record_id": None,
        "created_at": datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return ReminderRead(**base)


def test_run_chat_uses_record_tool_with_history() -> None:
    provider = MockProvider(
        turns=[
            ProviderTurn(
                tool_call=ToolCallRequest(
                    name="list_pet_records",
                    args={"pet_id": str(PET_ID), "record_type": "deworming"},
                )
            ),
            ProviderTurn(reply="上次驱虫是 2026-10-20。"),
        ]
    )
    history = [
        ChatHistoryMessage(role="user", content="上次驱虫是什么时候？"),
        ChatHistoryMessage(role="assistant", content="我来查一下记录。"),
    ]
    reply = run_chat(
        "上次驱虫是什么时候？",
        PET_ID,
        FakePetService(),
        record_service=FakeRecordService([_record()]),
        provider=provider,
        history=history,
    )
    assert reply.reply == "上次驱虫是 2026-10-20。"
    assert [t.name for t in reply.tool_calls] == ["list_pet_records"]
    assert reply.tool_calls[0].status == "success"


def test_run_chat_uses_reminder_tool() -> None:
    provider = MockProvider(
        turns=[
            ProviderTurn(
                tool_call=ToolCallRequest(
                    name="list_pet_reminders", args={"status": "pending"}
                )
            ),
            ProviderTurn(reply="这周有一次驱虫待办。"),
        ]
    )
    reply = run_chat(
        "这周有哪些安排？",
        PET_ID,
        FakePetService(),
        reminder_service=FakeReminderService([_reminder()]),
        provider=provider,
    )
    assert reply.reply == "这周有一次驱虫待办。"
    assert [t.name for t in reply.tool_calls] == ["list_pet_reminders"]
    assert reply.tool_calls[0].status == "success"


def test_run_chat_record_tool_error_status() -> None:
    provider = MockProvider(
        turns=[
            ProviderTurn(tool_call=ToolCallRequest(name="list_pet_records", args={})),
            ProviderTurn(reply="暂时无法查询记录。"),
        ]
    )
    reply = run_chat(
        "上次驱虫是什么时候？",
        PET_ID,
        FakePetService(),
        record_service=FailingRecordService(),
        provider=provider,
    )
    assert reply.tool_calls[0].status == "error"


def test_run_chat_without_services_does_not_register_p1_tools() -> None:
    provider = MockProvider(
        turns=[
            ProviderTurn(tool_call=ToolCallRequest(name="list_pet_records", args={})),
            ProviderTurn(reply="抱歉，暂时没有记录查询能力。"),
        ]
    )
    reply = run_chat(
        "上次驱虫是什么时候？",
        PET_ID,
        FakePetService(),
        provider=provider,
    )
    assert reply.tool_calls[0].status == "error"
