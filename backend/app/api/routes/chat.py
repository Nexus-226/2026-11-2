from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.chat import run_chat
from app.agent.errors import ProviderError
from app.agent.providers.base import LLMProvider
from app.agent.providers.factory import build_default_provider
from app.agent.schemas import ChatHistoryMessage
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat_service
from app.services.nearby_service import BoundNearbyService
from app.services.pet_service import BoundPetService
from app.services.record_service import BoundRecordService
from app.services.reminder_service import BoundReminderService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]

_PROVIDER_ERROR_STATUS = {
    "UPSTREAM_ERROR": 502,
    "SERVICE_UNAVAILABLE": 503,
    "UPSTREAM_TIMEOUT": 504,
}


def get_llm_provider() -> LLMProvider:
    """每个请求构建一个 Provider（有 key 用 Qwen，否则回退 Mock）。"""
    return build_default_provider()


LlmProvider = Annotated[LLMProvider, Depends(get_llm_provider)]


@router.post("", response_model=ChatResponse)
def create_chat(
    request: ChatRequest, session: DbSession, provider: LlmProvider
) -> ChatResponse:
    service = BoundPetService(session)
    record_service = BoundRecordService(session)
    reminder_service = BoundReminderService(session)
    nearby_service = BoundNearbyService()
    if request.pet_id is not None and service.get_pet(request.pet_id) is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PET_NOT_FOUND",
                "message": "未找到宠物",
                "retryable": False,
            },
        )

    chat_session = chat_service.get_or_create_chat_session(session, request.session_id)
    session_id = chat_session.id
    session.rollback()
    with chat_service.serialize_chat_session(session_id):
        history: list[ChatHistoryMessage]
        history, expected_sequence = chat_service.get_chat_history(
            session, chat_session, pet_id=request.pet_id
        )
        session.rollback()
        try:
            result = run_chat(
                request.message,
                request.pet_id,
                service,
                record_service=record_service,
                reminder_service=reminder_service,
                nearby_service=nearby_service,
                provider=provider,
                history=history,
            )
        except ProviderError as exc:
            raise HTTPException(
                status_code=_PROVIDER_ERROR_STATUS.get(exc.code, 502),
                detail={"code": exc.code, "message": exc.message, "retryable": True},
            ) from exc
        finally:
            session.rollback()

        try:
            assistant_message = chat_service.save_chat_turn(
                session,
                chat_session,
                session_id,
                message=request.message,
                pet_id=request.pet_id,
                reply=result,
                expected_sequence=expected_sequence,
            )
        except chat_service.ChatTurnConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "HTTP_ERROR",
                    "message": "会话内容已更新，请重新发送本轮",
                    "retryable": True,
                },
            ) from exc

    return ChatResponse(
        session_id=session_id,
        message_id=assistant_message.id,
        reply=result.reply,
        tool_calls=result.tool_calls,
    )
