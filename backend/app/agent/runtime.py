from uuid import uuid4

from app.agent.tools import Tool
from app.schemas import ChatRequest, ChatResponse, ToolStatus

MEDICAL_TERMS = ("生病", "呕吐", "腹泻", "发烧", "用药", "诊断", "疼", "没精神", "不吃")


class AgentRuntime:
    """Deterministic P0 runtime; response composition can later use an LLM provider."""

    def __init__(self, tools: dict[str, Tool]) -> None:
        self._tools = tools

    def chat(self, request: ChatRequest, request_id: str) -> ChatResponse:
        session_id = request.session_id or f"session_{uuid4().hex[:10]}"
        results = []
        pet_context = None
        if request.pet_id:
            result = self._tools["get_pet_profile"]({"user_id": request.user_id, "pet_id": request.pet_id})
            results.append(result)
            if result.status == ToolStatus.SUCCESS:
                pet_context = result.data

        if request.pet_id and not pet_context:
            reply = "我没能读取这只宠物的资料。请确认宠物仍存在，或先在宠物资料页选择一只宠物。"
        elif pet_context:
            details = [f"{pet_context['name']}是一只{pet_context['species']}"]
            if pet_context.get("breed"):
                details.append(f"品种为 {pet_context['breed']}")
            if pet_context.get("age_years") is not None:
                details.append(f"约 {pet_context['age_years']:g} 岁")
            if pet_context.get("health_notes"):
                details.append(f"已有备注：{pet_context['health_notes']}")
            reply = "，".join(details) + "。结合这些资料，我建议先记录具体症状、饮食和精神状态，再针对你的问题逐项判断。"
        else:
            reply = "我可以提供通用宠物护理建议；如果你选择一只宠物，我还能结合它的年龄、品种和健康备注回答。"

        if any(term in request.message for term in MEDICAL_TERMS):
            reply += " 以上仅供参考，不能替代兽医诊断；若症状严重、持续或突然恶化，请尽快联系专业兽医。"

        return ChatResponse(request_id=request_id, session_id=session_id, reply=reply, used_pet_id=request.pet_id if pet_context else None, tool_results=results)
