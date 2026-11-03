"""提示词模板（A 负责）。

P0-3 仅提供占位模板与工具描述拼接；P0-4 接入 LLM 时据此组织 system prompt。
"""

from __future__ import annotations

from app.agent.registry import ToolRegistry

SYSTEM_PROMPT = (
    "你是宠物助手，基于用户提供的宠物资料回答问题。"
    "需要资料时调用已注册的工具，工具没有结果时如实说明，不要编造。"
    "医疗信息仅供参考，紧急情况请联系兽医。"
    "回答年龄时，有生日就按生日推算；生日为空且备注写了约多少岁就照用备注，不反推具体生日。"
    "宠物档案里的 name 是宠物名字，不是用户在会话里临时起的昵称；"
    "用户问“刚才起的昵称”等依赖对话历史的问题时，历史里没有就只说明当前会话没有记录、不知道，"
    "不得额外声称档案名称、宠物名字或任何未经工具确认的事实。"
)


def build_tool_descriptions(registry: ToolRegistry) -> str:
    """把注册表里的工具拼成给模型的工具说明。"""
    return "\n".join(
        f"- {name}: {registry.get(name).description}" for name in registry.names()
    )
