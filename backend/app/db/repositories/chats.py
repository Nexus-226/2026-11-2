from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.chat import ChatReply
from app.db.models import DEFAULT_USER_ID, ChatMessage, ChatSession, utc_now


@dataclass(frozen=True)
class ChatHistoryEntry:
    role: Literal["user", "assistant"]
    content: str
    pet_id: UUID | None


class ChatHistoryConflict(Exception):
    """The conversation changed after its history was read."""


def get_chat_session(session: Session, session_id: UUID) -> ChatSession | None:
    return session.scalar(
        select(ChatSession).where(
            ChatSession.id == str(session_id),
            ChatSession.user_id == DEFAULT_USER_ID,
        )
    )


def get_chat_history(
    session: Session, session_id: str, pet_id: UUID | None
) -> tuple[list[ChatHistoryEntry], int]:
    messages = list(
        session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.sequence)
        )
    )
    last_sequence = messages[-1].sequence if messages else 0
    requested_pet_id = str(pet_id) if pet_id is not None else None
    history: list[ChatHistoryEntry] = []

    index = 0
    while index + 1 < len(messages):
        user_message = messages[index]
        assistant_message = messages[index + 1]
        is_complete_turn = (
            user_message.history_reliable
            and assistant_message.history_reliable
            and user_message.role == "user"
            and assistant_message.role == "assistant"
            and assistant_message.sequence == user_message.sequence + 1
            and user_message.pet_id == assistant_message.pet_id
        )
        if not is_complete_turn:
            index += 1
            continue

        if user_message.pet_id is None or user_message.pet_id == requested_pet_id:
            history.extend(
                [
                    ChatHistoryEntry(
                        role="user",
                        content=user_message.content,
                        pet_id=(
                            UUID(user_message.pet_id)
                            if user_message.pet_id is not None
                            else None
                        ),
                    ),
                    ChatHistoryEntry(
                        role="assistant",
                        content=assistant_message.content,
                        pet_id=(
                            UUID(assistant_message.pet_id)
                            if assistant_message.pet_id is not None
                            else None
                        ),
                    ),
                ]
            )
        index += 2

    return history, last_sequence


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
