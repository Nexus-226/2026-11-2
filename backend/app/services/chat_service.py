from _thread import LockType
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agent.chat import ChatReply
from app.db.models import ChatMessage, ChatSession
from app.db.repositories import chats as chat_repository

_session_locks_guard = Lock()
_session_locks: dict[str, tuple[LockType, int]] = {}


class ChatTurnConflict(Exception):
    """A concurrent request invalidated the history used for this turn."""


@contextmanager
def serialize_chat_session(session_id: str) -> Iterator[None]:
    """Serialize turns in this process; sequence checks still guard stale saves."""
    with _session_locks_guard:
        lock, references = _session_locks.get(session_id, (Lock(), 0))
        _session_locks[session_id] = (lock, references + 1)

    lock.acquire()
    try:
        yield
    finally:
        lock.release()
        with _session_locks_guard:
            _, references = _session_locks[session_id]
            if references == 1:
                del _session_locks[session_id]
            else:
                _session_locks[session_id] = (lock, references - 1)


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


def get_chat_history(
    session: Session, chat_session: ChatSession, *, pet_id: UUID | None
) -> tuple[list[chat_repository.ChatHistoryEntry], int]:
    return chat_repository.get_chat_history(session, chat_session.id, pet_id)


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
    try:
        return chat_repository.save_chat_turn(
            session,
            chat_session,
            session_id,
            message=message,
            pet_id=pet_id,
            reply=reply,
            expected_sequence=expected_sequence,
        )
    except chat_repository.ChatHistoryConflict as exc:
        raise ChatTurnConflict from exc
