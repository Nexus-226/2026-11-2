from app.agent.tools import build_tool_allowlist
from app.schemas import ToolStatus
from app.services.pet_service import PetService


def test_allowlist_is_explicit_and_validates_missing_pet() -> None:
    tools = build_tool_allowlist(PetService())
    assert set(tools) == {"get_pet_profile"}
    result = tools["get_pet_profile"]({"user_id": "demo-user", "pet_id": "missing"})
    assert result.status == ToolStatus.NOT_FOUND
