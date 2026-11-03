from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.chat import ChatReply
from app.db.models import DEFAULT_USER_ID, ChatMessage, ChatSession, utc_now


class ChatHistoryConflict(Exception):
    """The conversation changed after its history was read."""


def get_chat_session(session: Session, session_id: UUID) -> ChatSession | None:
    return session.scalar(
        select(ChatSession).where(
            ChatSession.id == str(session_id),
            ChatSession.user_id == DEFAULT_USER_ID,
        )
    )


def get_recent_chat_messages(
    session: Session, session_id: str, *, limit: int
) -> tuple[list[ChatMessage], int]:
    latest_sequence = (
        session.scalar(
            select(func.max(ChatMessage.sequence)).where(
                ChatMessage.session_id == session_id
            )
        )
        or 0
    )
    recent_message_ids = (
        select(ChatMessage.id)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.sequence.desc())
        .limit(limit)
        .subquery()
    )
    messages = list(
        session.scalars(
            select(ChatMessage)
            .join(recent_message_ids, ChatMessage.id == recent_message_ids.c.id)
            .order_by(ChatMessage.sequence)
        )
    )
    return messages, latest_sequence


def new_chat_session() -> ChatSession:
    return ChatSession(id=str(uuid4()), user_id=DEFAULT_USER_ID)


def save_chat_turn(
    session: Session,
    chat_session: ChatSession,
    session_id: str,
    *,
    message: str,
    pet_id: UUID | None,
    reply: ChatReply,
    expected_sequence: int,
) -> ChatMessage:
    user_message = ChatMessage(
        id=str(uuid4()),
        session_id=session_id,
        role="user",
        content=message,
        sequence=expected_sequence + 1,
        history_reliable=True,
        pet_id=str(pet_id) if pet_id is not None else None,
    )
    assistant_message = ChatMessage(
        id=str(uuid4()),
        session_id=session_id,
        role="assistant",
        content=reply.reply,
        sequence=expected_sequence + 2,
        history_reliable=True,
        pet_id=str(pet_id) if pet_id is not None else None,
        tool_calls=[call.model_dump() for call in reply.tool_calls],
    )

    try:
        with session.begin():
            latest_sequence = (
                session.scalar(
                    select(func.max(ChatMessage.sequence)).where(
                        ChatMessage.session_id == session_id
                    )
                )
                or 0
            )
            if latest_sequence != expected_sequence:
                raise ChatHistoryConflict

            chat_session.updated_at = utc_now()
            session.add_all([chat_session, user_message, assistant_message])
    except IntegrityError as exc:
        constraint_name = getattr(
            getattr(exc.orig, "diag", None), "constraint_name", None
        )
        if constraint_name == "uq_chat_messages_session_sequence" or (
            "UNIQUE constraint failed: "
            "chat_messages.session_id, chat_messages.sequence" in str(exc.orig)
        ):
            raise ChatHistoryConflict from exc
        raise

    return assistant_message
