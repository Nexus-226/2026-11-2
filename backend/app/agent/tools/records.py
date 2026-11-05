"""P1 日常记录只读工具（A 定义）。

工具绑定本次请求的关联宠物（``current_pet_id``），默认只查当前宠物；未关联时
要求先选择，跨宠物汇总需显式 ``all_pets=true``。无匹配返回空列表，失败由 Service
抛出可识别异常，由 Runtime 映射为 error 结果，不把失败伪装成空列表。
"""

from __future__ import annotations

from uuid import UUID

from app.agent.errors import DomainError
from app.agent.registry import Tool
from app.agent.schemas import ListPetRecordsInput, RecordDraft
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
                "用户明确要求汇总所有宠物时才传 all_pets=true，此时返回全部宠物及未关联数据，"
                "每条结果保留 pet_id 归属。"
                "体重记录含 weight_kg（单位公斤）。"
                "无匹配返回空列表；查询失败会返回错误，不要把失败说成没有记录。"
            ),
            input_schema=ListPetRecordsInput,
            func=list_pet_records,
        ),
    ]


def make_record_draft_tool() -> Tool:
    """P2：生成洗澡记录草稿的工具（只读，不写入）。

    模型在宠物与日期都明确后调用，参数即草稿；``func`` 原样返回入参，由
    ``run_chat`` 捕获为 ``ChatReply.draft``，页面确认后才由前端提交保存。
    """

    def propose_record_draft(inp: RecordDraft) -> RecordDraft:
        return inp

    return Tool(
        name="propose_record_draft",
        description=(
            "当用户明确要求记录一次已经发生的洗澡，且宠物、日期都已明确时，"
            "生成一条洗澡记录草稿。只支持 record_type=bath（洗澡）；"
            "occurred_on 为实际发生日期（Asia/Shanghai 日历日），不得晚于今天；"
            "pet_id 必须是已登记宠物的 UUID，可通过 get_pet_profile 或 list_pets 确认。"
            "name 通常留空，notes 可选（记录洗浴用品或备注等）。"
            "本工具只生成草稿，不保存记录，保存由用户在页面确认后完成。"
            "宠物不明确、同名或日期含糊（如未来、记不清）时必须先向用户澄清，不要调用本工具。"
        ),
        input_schema=RecordDraft,
        func=propose_record_draft,
    )
