"""Agent 对话编排（A 负责）。

``run_chat`` 是给 B 的 ``/api/v1/chat`` 路由调用的入口：B 传入 message、pet_id、
绑定好 DB session 的 PetService，以及按会话读取的历史消息；这里驱动 LLM Provider
→ 工具调用 → 结果回填 → 最终回复，返回 reply 和 tool_calls。session_id /
message_id / 历史持久化由 B 负责。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.providers.base import LLMProvider
from app.agent.providers.factory import build_default_provider
from app.agent.runtime import MAX_TOOL_CALLS_PER_TURN, AgentRuntime
from app.agent.schemas import ChatHistoryMessage, RecordDraft, ToolResult
from app.agent.service_protocol import (
    NearbyService,
    PetService,
    RecordService,
    ReminderService,
)
from app.agent.tools import build_default_registry
from app.schemas.pet import PetRead

# 最近 10 个完整轮次（20 条消息）；字符数只是保守预算，给系统提示、本次问题、
# 工具定义、当前工具结果和输出预留空间，不视为精确 token 计数。
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CHARS = 8000

# P2：生成洗澡记录草稿的工具名；run_chat 捕获其成功参数作为 ChatReply.draft。
RECORD_DRAFT_TOOL = "propose_record_draft"


class ToolCallSummary(BaseModel):
    """chat 响应里的 tool_calls 项：只暴露名称和状态，不泄露参数/结果。"""

    name: str
    status: Literal["success", "error"]


class ChatReply(BaseModel):
    """run_chat 返回的内容；session_id / message_id 由 B 补充。"""

    reply: str
    tool_calls: list[ToolCallSummary] = Field(default_factory=list)
    draft: RecordDraft | None = None


def _select_history(
    history: list[ChatHistoryMessage] | None,
    pet_id: UUID | None,
) -> list[ChatHistoryMessage]:
    """取最近若干完整轮次，并限制总字符数；不保留半轮消息。

    只保留通用消息（pet_id 为 None）或与当前请求关联宠物一致的历史；未关联宠物
    时不从历史恢复旧宠物上下文，避免旧宠物事实混入本轮。
    """
    messages = [
        item
        for item in history or []
        if item.content.strip() and (item.pet_id is None or item.pet_id == pet_id)
    ]
    if not messages:
        return []

    messages = messages[-MAX_HISTORY_MESSAGES:]

    selected: list[ChatHistoryMessage] = []
    total_chars = 0
    for item in reversed(messages):
        if selected and total_chars + len(item.content) > MAX_HISTORY_CHARS:
            break
        selected.append(item)
        total_chars += len(item.content)
    selected.reverse()

    # 只保留完整轮次：去掉开头孤立的 assistant 和结尾没有回复的 user。
    while selected and selected[0].role == "assistant":
        selected.pop(0)
    while selected and selected[-1].role == "user":
        selected.pop()
    return selected


def _associated_pet_species(pet: PetRead) -> str:
    """关联宠物的物种说明，沿用 other/other_species 语义。"""
    if pet.species == "other":
        if pet.other_species:
            return f"other（具体物种：{pet.other_species}）"
        return "other（未填具体物种）"
    return pet.species


def run_chat(
    message: str,
    pet_id: UUID | None,
    service: PetService,
    *,
    record_service: RecordService | None = None,
    reminder_service: ReminderService | None = None,
    nearby_service: NearbyService | None = None,
    provider: LLMProvider | None = None,
    max_tool_calls: int = MAX_TOOL_CALLS_PER_TURN,
    history: list[ChatHistoryMessage] | None = None,
) -> ChatReply:
    registry = build_default_registry(
        service,
        record_service=record_service,
        reminder_service=reminder_service,
        nearby_service=nearby_service,
        current_pet_id=pet_id,
    )
    runtime = AgentRuntime(registry, max_tool_calls=max_tool_calls)
    provider = provider or build_default_provider()
    tools = [registry.get(name) for name in registry.names()]
    selected_history = _select_history(history, pet_id)

    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    next7_end = today + timedelta(days=6)
    system = (
        SYSTEM_PROMPT
        + f" 今天是 {today.isoformat()}（星期{weekday_names[today.weekday()]}，Asia/Shanghai）。"
        + f" “未来七天”指 {today.isoformat()} 至 {next7_end.isoformat()}（含今天，共七天）；"
        + f" “本周”指 {monday.isoformat()}（周一）至 {sunday.isoformat()}（周日）。"
    )
    if pet_id is not None:
        associated_pet = service.get_pet(pet_id)
        if associated_pet is not None:
            species = _associated_pet_species(associated_pet)
            system += (
                f" 当前关联宠物：名字「{associated_pet.name}」，"
                f"species={species}，pet_id={pet_id}。"
                f"当用户提到这只宠物的名字「{associated_pet.name}」，"
                "或“它/这只宠物/当前宠物”时，优先按这只关联宠物理解并回答；"
                "用户提到的是其他名字时，不要自动当成这只关联宠物，也不要未查询就断言"
                "档案里没有该名字：先调用 list_pets 核对是否有这只宠物，"
                "列表里确实没有时再如实说明没有。需要档案详情时调用 get_pet_profile 查询。"
            )
            same_name_pets = [
                p for p in service.list_pets() if p.name == associated_pet.name
            ]
            if len(same_name_pets) > 1:
                system += (
                    f" 注意：档案里目前有 {len(same_name_pets)} 只名字都为"
                    f"「{associated_pet.name}」的宠物。用户只提这个名字、且没有用"
                    "“它/这只宠物/当前宠物”明确指向当前关联的这只时，不能默认就是它："
                    "先调用 list_pets 列出这些同名宠物（按 species 区分），"
                    "请用户确认是哪一只后再回答或生成记录草稿；确认前不要生成草稿。"
                )
        else:
            system += f" 当前关联宠物 pet_id={pet_id}。"
    else:
        system += (
            " 当前未关联任何宠物；用户用“它/这只宠物/当前宠物”指代时，"
            "先请用户选择宠物，不要用全部宠物列表代替当前宠物。"
        )

    summaries: list[ToolCallSummary] = []
    results: list[ToolResult] = []
    tool_call_count = 0
    draft: RecordDraft | None = None

    while True:
        turn = provider.next_turn(
            system_prompt=system,
            user_message=message,
            tools=tools,
            tool_results=results,
            # 只在首轮拼接历史；同次请求的工具循环继续追加调用与结果。
            history=selected_history if tool_call_count == 0 else None,
        )
        if turn.reply is not None:
            return ChatReply(reply=turn.reply, tool_calls=summaries, draft=draft)
        if turn.tool_call is None:
            return ChatReply(
                reply="抱歉，我暂时无法回答。", tool_calls=summaries, draft=draft
            )
        if tool_call_count >= max_tool_calls:
            return ChatReply(
                reply="抱歉，这个问题需要更多信息，我暂时无法回答。",
                tool_calls=summaries,
                draft=draft,
            )
        result = runtime.run_tools([turn.tool_call])[0]
        tool_call_count += 1
        results.append(result)
        summaries.append(ToolCallSummary(name=result.name, status=result.status))
        if (
            turn.tool_call.name == RECORD_DRAFT_TOOL
            and result.status == "success"
            and isinstance(result.data, RecordDraft)
        ):
            draft = result.data
