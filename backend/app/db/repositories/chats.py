from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.chat import ChatReply
from app.db.models import DEFAULT_USER_ID, ChatMessage, ChatSession, utc_now


def get_chat_session(session: Session, session_id: UUID) -> ChatSession | None:
    return session.scalar(
        select(ChatSession).where(
            ChatSession.id == str(session_id),
            ChatSession.user_id == DEFAULT_USER_ID,
        )
    )


def new_chat_session() -> ChatSession:
    return ChatSession(id=str(uuid4()), user_id=DEFAULT_USER_ID)


def save_chat_turn(
    session: Session,
    chat_session: ChatSession,
    *,
    message: str,
    pet_id: UUID | None,
    reply: ChatReply,
) -> ChatMessage:
    assistant_message = ChatMessage(
        id=str(uuid4()),
        session_id=chat_session.id,
        role="assistant",
        content=reply.reply,
        pet_id=str(pet_id) if pet_id is not None else None,
        tool_calls=[call.model_dump() for call in reply.tool_calls],
    )
    session.add_all(
        [
            chat_session,
            ChatMessage(
                id=str(uuid4()),
                session_id=chat_session.id,
                role="user",
                content=message,
                pet_id=str(pet_id) if pet_id is not None else None,
            ),
            assistant_message,
        ]
    )
    chat_session.updated_at = utc_now()
    session.commit()
    session.refresh(assistant_message)
    return assistant_message
