from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agent.chat import ChatReply
from app.db.models import ChatMessage, ChatSession
from app.db.repositories import chats as chat_repository


def get_or_create_chat_session(
    session: Session, session_id: UUID | None
) -> ChatSession:
    if session_id is None:
        return chat_repository.new_chat_session()

    chat_session = chat_repository.get_chat_session(session, session_id)
    if chat_session is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SESSION_NOT_FOUND",
                "message": "未找到会话",
                "retryable": False,
            },
        )
    return chat_session


def save_chat_turn(
    session: Session,
    chat_session: ChatSession,
    *,
    message: str,
    pet_id: UUID | None,
    reply: ChatReply,
) -> ChatMessage:
    return chat_repository.save_chat_turn(
        session,
        chat_session,
        message=message,
        pet_id=pet_id,
        reply=reply,
    )
