from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from app.agent.errors import DomainError
from app.agent.runtime import AgentRuntime
from app.agent.schemas import ToolCallRequest
from app.agent.tools import build_default_registry
from app.schemas.pet import PetRead
from app.schemas.record import RecordRead
from app.schemas.reminder import ReminderRead

PET_ID = UUID("b8f34f24-f5cf-4b5c-8d40-073541725a11")


class FakePetService:
    """仅用于满足 build_default_registry 的 PetService 参数。"""

    def get_pet(self, pet_id: UUID) -> PetRead | None:
        return None

    def list_pets(self) -> list[PetRead]:
        return []


class FakeRecordService:
    def __init__(self, records: list[RecordRead] | None = None) -> None:
        self._records = list(records or [])

    def list_records(
        self,
        *,
        pet_id: UUID | None = None,
        record_type: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[RecordRead]:
        result = self._records
        if pet_id is not None:
            result = [r for r in result if r.pet_id == pet_id]
        if record_type is not None:
            result = [r for r in result if r.record_type == record_type]
        if from_date is not None:
            result = [r for r in result if r.occurred_on >= from_date]
        if to_date is not None:
            result = [r for r in result if r.occurred_on <= to_date]
        return result


class FakeReminderService:
    def __init__(self, reminders: list[ReminderRead] | None = None) -> None:
        self._reminders = list(reminders or [])

    def list_reminders(
        self,
        *,
        pet_id: UUID | None = None,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[ReminderRead]:
        result = self._reminders
        if pet_id is not None:
            result = [r for r in result if r.pet_id == pet_id]
        if status is not None:
            result = [r for r in result if r.status == status]
        if from_date is not None:
            result = [r for r in result if r.due_on >= from_date]
        if to_date is not None:
            result = [r for r in result if r.due_on <= to_date]
        return result


class FailingRecordService:
    """查询失败必须抛异常，而不是返回空列表。"""

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


def _runtime(
    *,
    record_service: object = FakeRecordService(),
    reminder_service: object = FakeReminderService(),
    current_pet_id: UUID | None = PET_ID,
) -> AgentRuntime:
    registry = build_default_registry(
        FakePetService(),
        record_service=record_service,  # type: ignore[arg-type]
        reminder_service=reminder_service,  # type: ignore[arg-type]
        current_pet_id=current_pet_id,
    )
    return AgentRuntime(registry)


def test_list_pet_records_returns_records() -> None:
    runtime = _runtime(record_service=FakeRecordService([_record()]))
    result = runtime.run_tools([ToolCallRequest(name="list_pet_records", args={})])[0]
    assert result.status == "success"
    assert isinstance(result.data, list)
    assert result.data[0].record_type == "deworming"
    assert result.data[0].occurred_on == date(2026, 10, 20)


def test_list_pet_records_empty_returns_empty_list() -> None:
    runtime = _runtime(record_service=FakeRecordService([]))
    result = runtime.run_tools([ToolCallRequest(name="list_pet_records", args={})])[0]
    assert result.status == "success"
    assert result.data == []


def test_list_pet_records_filters_by_type_and_date() -> None:
    records = [
        _record(record_type="deworming", occurred_on=date(2026, 10, 20)),
        _record(record_type="bath", occurred_on=date(2026, 10, 25)),
    ]
    runtime = _runtime(record_service=FakeRecordService(records))
    result = runtime.run_tools(
        [ToolCallRequest(name="list_pet_records", args={"record_type": "bath"})]
    )[0]
    assert result.status == "success"
    assert [r.record_type for r in result.data] == ["bath"]


def test_list_pet_reminders_expose_due_group() -> None:
    reminders = [
        _reminder(),
        _reminder(title="已完成", status="completed"),
    ]
    runtime = _runtime(reminder_service=FakeReminderService(reminders))
    result = runtime.run_tools([ToolCallRequest(name="list_pet_reminders", args={})])[0]
    assert result.status == "success"
    by_status = {r.status: r for r in result.data}
    assert by_status["pending"].due_group in {"overdue", "today", "upcoming", "later"}
    assert by_status["completed"].due_group is None


def test_list_pet_reminders_empty_returns_empty_list() -> None:
    runtime = _runtime(reminder_service=FakeReminderService([]))
    result = runtime.run_tools([ToolCallRequest(name="list_pet_reminders", args={})])[0]
    assert result.status == "success"
    assert result.data == []


def test_record_service_failure_is_error_not_empty() -> None:
    runtime = _runtime(record_service=FailingRecordService())
    result = runtime.run_tools([ToolCallRequest(name="list_pet_records", args={})])[0]
    assert result.status == "error"
    assert result.error_code == "UPSTREAM_ERROR"


def test_invalid_record_type_is_validation_error() -> None:
    runtime = _runtime()
    result = runtime.run_tools(
        [ToolCallRequest(name="list_pet_records", args={"record_type": "unknown"})]
    )[0]
    assert result.status == "error"
    assert result.error_code == "VALIDATION_ERROR"


def test_tools_absent_without_service() -> None:
    registry = build_default_registry(FakePetService())
    names = registry.names()
    assert "list_pet_records" not in names
    assert "list_pet_reminders" not in names


def test_list_pet_records_is_bound_to_current_pet() -> None:
    other_pet = uuid4()
    records = [
        _record(),  # PET_ID
        _record(pet_id=other_pet, record_type="bath"),
    ]
    runtime = _runtime(record_service=FakeRecordService(records))
    result = runtime.run_tools([ToolCallRequest(name="list_pet_records", args={})])[0]
    assert result.status == "success"
    assert [r.pet_id for r in result.data] == [PET_ID]


def test_from_date_after_to_date_is_validation_error() -> None:
    runtime = _runtime()
    result = runtime.run_tools(
        [
            ToolCallRequest(
                name="list_pet_records",
                args={"from_date": "2026-11-09", "to_date": "2026-11-02"},
            )
        ]
    )[0]
    assert result.status == "error"
    assert result.error_code == "VALIDATION_ERROR"


def test_list_pet_records_requires_pet_when_unlinked() -> None:
    runtime = _runtime(
        record_service=FakeRecordService([_record()]), current_pet_id=None
    )
    result = runtime.run_tools([ToolCallRequest(name="list_pet_records", args={})])[0]
    assert result.status == "error"
    assert result.error_code == "NO_PET_SELECTED"


def test_list_pet_reminders_requires_pet_when_unlinked() -> None:
    runtime = _runtime(
        reminder_service=FakeReminderService([_reminder()]), current_pet_id=None
    )
    result = runtime.run_tools([ToolCallRequest(name="list_pet_reminders", args={})])[0]
    assert result.status == "error"
    assert result.error_code == "NO_PET_SELECTED"


def test_list_pet_records_all_pets_queries_all() -> None:
    other_pet = uuid4()
    records = [
        _record(),  # PET_ID
        _record(pet_id=other_pet, record_type="bath"),
    ]
    runtime = _runtime(record_service=FakeRecordService(records))
    result = runtime.run_tools(
        [ToolCallRequest(name="list_pet_records", args={"all_pets": True})]
    )[0]
    assert result.status == "success"
    assert {r.pet_id for r in result.data} == {PET_ID, other_pet}


def test_list_pet_reminders_all_pets_queries_all() -> None:
    other_pet = uuid4()
    reminders = [
        _reminder(),  # PET_ID
        _reminder(pet_id=other_pet, title="另一只宠物的提醒"),
    ]
    runtime = _runtime(reminder_service=FakeReminderService(reminders))
    result = runtime.run_tools(
        [ToolCallRequest(name="list_pet_reminders", args={"all_pets": True})]
    )[0]
    assert result.status == "success"
    assert {r.pet_id for r in result.data} == {PET_ID, other_pet}
