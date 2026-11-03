"""P1 站内提醒只读工具（A 定义）。

提醒表示“计划发生”，与实际护理记录分开；``due_group`` 由 B 的 Service 计算，
Agent 只读取该派生字段，不自行按日期分组。工具绑定本次请求的关联宠物，默认只查
当前宠物；未关联时要求先选择，跨宠物汇总需显式 ``all_pets=true``。
"""

from __future__ import annotations

from uuid import UUID

from app.agent.errors import DomainError
from app.agent.registry import Tool
from app.agent.schemas import ListPetRemindersInput
from app.agent.service_protocol import ReminderService
from app.schemas.reminder import ReminderRead


def make_reminder_tools(
    service: ReminderService, current_pet_id: UUID | None
) -> list[Tool]:
    """基于 Service 构造提醒查询工具；``current_pet_id`` 为本次请求的关联宠物。"""

    def list_pet_reminders(inp: ListPetRemindersInput) -> list[ReminderRead]:
        if not inp.all_pets and current_pet_id is None:
            raise DomainError("NO_PET_SELECTED", "请先选择宠物")
        pet_id = None if inp.all_pets else current_pet_id
        return service.list_reminders(
            pet_id=pet_id,
            status=inp.status,
            from_date=inp.from_date,
            to_date=inp.to_date,
        )

    return [
        Tool(
            name="list_pet_reminders",
            description=(
                "查询计划发生的待办提醒。每条提醒含 due_on（到期日）和 due_group（overdue 逾期 / "
                "today 今天 / upcoming 明日至第七日 / later 第七日之后；已完成或已取消为 null）。"
                "默认只查当前关联宠物；未关联宠物时先请用户选择。"
                "用户明确要求汇总所有宠物时才传 all_pets=true，此时返回全部宠物及未关联数据，"
                "每条结果保留 pet_id 归属。"
                "提醒是计划，不等于已经做过的护理记录；“未来七天”“这周”的起止日期见系统提示。"
                "无匹配返回空列表；查询失败会返回错误。"
            ),
            input_schema=ListPetRemindersInput,
            func=list_pet_reminders,
        ),
    ]
