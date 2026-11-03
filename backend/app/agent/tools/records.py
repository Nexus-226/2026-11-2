"""P1 日常记录只读工具（A 定义）。

工具绑定本次请求的关联宠物（``current_pet_id``），默认只查当前宠物；未关联时
要求先选择，跨宠物汇总需显式 ``all_pets=true``。无匹配返回空列表，失败由 Service
抛出可识别异常，由 Runtime 映射为 error 结果，不把失败伪装成空列表。
"""

from __future__ import annotations

from uuid import UUID

from app.agent.errors import DomainError
from app.agent.registry import Tool
from app.agent.schemas import ListPetRecordsInput
from app.agent.service_protocol import RecordService
from app.schemas.record import RecordRead


def make_record_tools(
    service: RecordService, current_pet_id: UUID | None
) -> list[Tool]:
    """基于 Service 构造记录查询工具；``current_pet_id`` 为本次请求的关联宠物。"""

    def list_pet_records(inp: ListPetRecordsInput) -> list[RecordRead]:
        if not inp.all_pets and current_pet_id is None:
            raise DomainError("NO_PET_SELECTED", "请先选择宠物")
        pet_id = None if inp.all_pets else current_pet_id
        return service.list_records(
            pet_id=pet_id,
            record_type=inp.record_type,
            from_date=inp.from_date,
            to_date=inp.to_date,
        )

    return [
        Tool(
            name="list_pet_records",
            description=(
                "查询已经发生的日常记录：vaccine 疫苗、deworming 驱虫、bath 洗澡、"
                "weight 体重。默认只查当前关联宠物；未关联宠物时先请用户选择。"
                "用户明确要求汇总所有宠物时才传 all_pets=true。"
                "体重记录含 weight_kg（单位公斤）。"
                "无匹配返回空列表；查询失败会返回错误，不要把失败说成没有记录。"
            ),
            input_schema=ListPetRecordsInput,
            func=list_pet_records,
        ),
    ]
