from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.chat import run_chat
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat_service
from app.services.pet_service import BoundPetService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=ChatResponse)
def create_chat(request: ChatRequest, session: DbSession) -> ChatResponse:
    service = BoundPetService(session)
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
    result = run_chat(request.message, request.pet_id, service)
    assistant_message = chat_service.save_chat_turn(
        session,
        chat_session,
        message=request.message,
        pet_id=request.pet_id,
        reply=result,
    )
    return ChatResponse(
        session_id=chat_session.id,
        message_id=assistant_message.id,
        reply=result.reply,
        tool_calls=result.tool_calls,
    )
