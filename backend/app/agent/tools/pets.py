"""P0 宠物资料工具（A 定义）。

工具只声明输入 Schema 并通过 Service 取数；不存在时抛 DomainError，
由 Runtime 映射为可识别的 PET_NOT_FOUND，不编造结果。
"""

from __future__ import annotations

from app.agent.errors import DomainError
from app.agent.registry import Tool
from app.agent.schemas import GetPetProfileInput, ListPetsInput
from app.agent.service_protocol import PetService
from app.schemas.pet import PetRead


def make_pet_tools(service: PetService) -> list[Tool]:
    """基于 Service 构造宠物资料工具。"""

    def get_pet_profile(inp: GetPetProfileInput) -> PetRead:
        pet = service.get_pet(inp.pet_id)
        if pet is None:
            raise DomainError("PET_NOT_FOUND", "未找到宠物")
        return pet

    def list_pets(_inp: ListPetsInput) -> list[PetRead]:
        return service.list_pets()

    return [
        Tool(
            name="get_pet_profile",
            description=(
                "按 pet_id 读取单个宠物资料；species 为 other 时，具体物种在 "
                "other_species 字段。"
            ),
            input_schema=GetPetProfileInput,
            func=get_pet_profile,
        ),
        Tool(
            name="list_pets",
            description=(
                "列出全部宠物资料，无结果返回空列表；每条含 species 与 other_species，"
                "other 宠物具体物种见 other_species。"
            ),
            input_schema=ListPetsInput,
            func=list_pets,
        ),
    ]
