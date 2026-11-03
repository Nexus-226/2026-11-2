"""P1 日常记录只读工具（A 定义）。

工具只声明输入 Schema 并通过 Service 取数；无匹配返回空列表，失败由 Service
抛出可识别异常，由 Runtime 映射为 error 结果，不把失败伪装成空列表。
"""

from __future__ import annotations

from app.agent.registry import Tool
from app.agent.schemas import ListPetRecordsInput
from app.agent.service_protocol import RecordService
from app.schemas.record import RecordRead


def make_record_tools(service: RecordService) -> list[Tool]:
    """基于 Service 构造记录查询工具。"""

    def list_pet_records(inp: ListPetRecordsInput) -> list[RecordRead]:
        return service.list_records(
            pet_id=inp.pet_id,
            record_type=inp.record_type,
            from_date=inp.from_date,
            to_date=inp.to_date,
        )

    return [
        Tool(
            name="list_pet_records",
            description=(
                "按宠物、记录类型和日期范围查询已经发生的日常记录："
                "vaccine 疫苗、deworming 驱虫、bath 洗澡、weight 体重。"
                "体重记录含 weight_kg（单位公斤）。"
                "无匹配返回空列表；查询失败会返回错误，不要把失败说成没有记录。"
            ),
            input_schema=ListPetRecordsInput,
            func=list_pet_records,
        ),
    ]
