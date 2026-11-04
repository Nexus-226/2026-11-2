from datetime import date, datetime, timezone
from uuid import UUID

from app.agent.runtime import AgentRuntime
from app.agent.schemas import ToolCallRequest
from app.agent.tools import build_default_registry
from app.schemas.pet import PetRead

PET_ID = UUID("b8f34f24-f5cf-4b5c-8d40-073541725a11")


class FakePetService:
    """测试用的宠物 Service，替代 B 尚未实现的真实实现。"""

    def __init__(self, pets: list[PetRead] | None = None) -> None:
        self._pets = {p.id: p for p in (pets or [])}

    def get_pet(self, pet_id: UUID) -> PetRead | None:
        return self._pets.get(pet_id)

    def list_pets(self) -> list[PetRead]:
        return list(self._pets.values())


def _pet(**overrides: object) -> PetRead:
    base: dict[str, object] = {
        "id": PET_ID,
        "name": "豆豆",
        "species": "dog",
        "other_species": None,
        "breed": "金毛",
        "birthday": date(2023, 5, 1),
        "notes": "对鸡肉过敏",
        "created_at": datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return PetRead(**base)


def test_get_pet_profile_returns_pet() -> None:
    runtime = AgentRuntime(build_default_registry(FakePetService([_pet()])))
    result = runtime.run_tools(
        [ToolCallRequest(name="get_pet_profile", args={"pet_id": str(PET_ID)})]
    )[0]
    assert result.status == "success"
    assert isinstance(result.data, PetRead)
    assert result.data.name == "豆豆"


def test_get_pet_profile_not_found_is_error_not_fabricated() -> None:
    runtime = AgentRuntime(build_default_registry(FakePetService([])))
    result = runtime.run_tools(
        [ToolCallRequest(name="get_pet_profile", args={"pet_id": str(PET_ID)})]
    )[0]
    assert result.status == "error"
    assert result.error_code == "PET_NOT_FOUND"


def test_list_pets_empty_returns_empty_list() -> None:
    runtime = AgentRuntime(build_default_registry(FakePetService([])))
    result = runtime.run_tools([ToolCallRequest(name="list_pets", args={})])[0]
    assert result.status == "success"
    assert result.data == []


def test_invalid_args_returns_validation_error() -> None:
    runtime = AgentRuntime(build_default_registry(FakePetService([_pet()])))
    result = runtime.run_tools(
        [ToolCallRequest(name="get_pet_profile", args={"pet_id": "not-a-uuid"})]
    )[0]
    assert result.status == "error"
    assert result.error_code == "VALIDATION_ERROR"


def test_unknown_tool_returns_tool_not_found() -> None:
    runtime = AgentRuntime(build_default_registry(FakePetService([])))
    result = runtime.run_tools([ToolCallRequest(name="does_not_exist", args={})])[0]
    assert result.status == "error"
    assert result.error_code == "TOOL_NOT_FOUND"


def test_runtime_enforces_max_tool_calls() -> None:
    runtime = AgentRuntime(build_default_registry(FakePetService([])))
    calls = [ToolCallRequest(name="list_pets", args={}) for _ in range(5)]
    results = runtime.run_tools(calls)
    assert len(results) == 3  # 超出上限的部分被丢弃，不执行
