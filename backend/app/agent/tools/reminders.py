"""P1 站内提醒只读工具（A 定义）。

提醒表示“计划发生”，与实际护理记录分开；``due_group`` 由 B 的 Service 计算，
Agent 只读取该派生字段，不自行按日期分组。
"""

from __future__ import annotations

from app.agent.registry import Tool
from app.agent.schemas import ListPetRemindersInput
from app.agent.service_protocol import ReminderService
from app.schemas.reminder import ReminderRead


def make_reminder_tools(service: ReminderService) -> list[Tool]:
    """基于 Service 构造提醒查询工具。"""

    def list_pet_reminders(inp: ListPetRemindersInput) -> list[ReminderRead]:
        return service.list_reminders(
            pet_id=inp.pet_id,
            status=inp.status,
            from_date=inp.from_date,
            to_date=inp.to_date,
        )

    return [
        Tool(
            name="list_pet_reminders",
            description=(
                "按宠物、状态和日期范围（from_date/to_date，含首尾）查询计划发生的待办提醒。"
                "每条提醒含 due_on（到期日）和 due_group（overdue 逾期 / today 今天 / "
                "upcoming 明日至第七日 / later 第七日之后；已完成或已取消的提醒为 null）。"
                "提醒是计划，不等于已经做过的护理记录；“未来七天”“这周”的起止日期见系统提示。"
                "无匹配返回空列表；查询失败会返回错误。"
            ),
            input_schema=ListPetRemindersInput,
            func=list_pet_reminders,
        ),
    ]
