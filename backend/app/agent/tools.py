from collections.abc import Callable

from pydantic import BaseModel, ValidationError

from app.schemas import ToolResult, ToolStatus
from app.services.pet_service import PetService


class GetPetProfileArgs(BaseModel):
    user_id: str
    pet_id: str


Tool = Callable[[dict[str, object]], ToolResult]


def build_tool_allowlist(pets: PetService) -> dict[str, Tool]:
    def get_pet_profile(raw: dict[str, object]) -> ToolResult:
        try:
            args = GetPetProfileArgs.model_validate(raw)
        except ValidationError as exc:
            return ToolResult(tool="get_pet_profile", status=ToolStatus.INVALID_INPUT, message=str(exc))
        pet = pets.get(args.user_id, args.pet_id)
        if not pet:
            return ToolResult(tool="get_pet_profile", status=ToolStatus.NOT_FOUND, message="Pet was not found for the demo user")
        return ToolResult(tool="get_pet_profile", status=ToolStatus.SUCCESS, data=pet.model_dump())

    return {"get_pet_profile": get_pet_profile}
