from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.chat import ChatReply
from app.db.models import Base, ChatMessage, ChatSession
from app.db.repositories.chats import (
    ChatHistoryConflict,
    get_chat_history,
    new_chat_session,
    save_chat_turn,
)


@pytest.fixture
def chat_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'chat_repository.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _save_turn(
    session: Session,
    chat_session: ChatSession,
    session_id: str,
    message: str,
    reply: str,
    expected_sequence: int,
    pet_id=None,
) -> None:
    save_chat_turn(
        session,
        chat_session,
        session_id,
        message=message,
        pet_id=pet_id,
        reply=ChatReply(reply=reply),
        expected_sequence=expected_sequence,
    )


def test_saves_turn_atomically_with_contiguous_sequence(chat_engine) -> None:
    chat_session = new_chat_session()
    session_id = chat_session.id
    with Session(chat_engine, expire_on_commit=False) as session:
        _save_turn(session, chat_session, session_id, "first", "answer", 0)
        _save_turn(session, chat_session, session_id, "second", "answer 2", 2)

    with Session(chat_engine) as session:
        messages = list(
            session.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.sequence)
            )
        )
    assert [(message.role, message.sequence) for message in messages] == [
        ("user", 1),
        ("assistant", 2),
        ("user", 3),
        ("assistant", 4),
    ]


def test_rejects_stale_history_without_saving_a_turn(chat_engine) -> None:
    chat_session = new_chat_session()
    session_id = chat_session.id
    with Session(chat_engine, expire_on_commit=False) as session:
        _save_turn(session, chat_session, session_id, "first", "answer", 0)
        with pytest.raises(ChatHistoryConflict):
            _save_turn(session, chat_session, session_id, "stale", "stale answer", 0)

    with Session(chat_engine) as session:
        messages = list(
            session.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.sequence)
            )
        )
    assert [(message.role, message.sequence) for message in messages] == [
        ("user", 1),
        ("assistant", 2),
    ]


def test_assistant_insert_failure_rolls_back_whole_turn(chat_engine) -> None:
    chat_session = new_chat_session()
    session_id = chat_session.id
    with chat_engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER reject_assistant BEFORE INSERT ON chat_messages "
            "WHEN NEW.role = 'assistant' BEGIN "
            "SELECT RAISE(ABORT, 'test failure'); END"
        )

    with (
        Session(chat_engine, expire_on_commit=False) as session,
        pytest.raises(IntegrityError),
    ):
        _save_turn(session, chat_session, session_id, "question", "answer", 0)

    with Session(chat_engine) as session:
        assert session.scalar(select(ChatSession.id)) is None
        assert session.scalar(select(ChatMessage.id)) is None


def test_history_only_includes_complete_reliable_pet_compatible_turns(
    chat_engine,
) -> None:
    chat_session = new_chat_session()
    session_id = chat_session.id
    pet_id = str(uuid4())
    with Session(chat_engine) as session:
        session.add(chat_session)
        session.add_all(
            [
                ChatMessage(
                    id=str(uuid4()),
                    session_id=session_id,
                    role="user",
                    content="pet-specific",
                    sequence=1,
                    history_reliable=True,
                    pet_id=pet_id,
                ),
                ChatMessage(
                    id=str(uuid4()),
                    session_id=session_id,
                    role="assistant",
                    content="pet answer",
                    sequence=2,
                    history_reliable=True,
                    pet_id=pet_id,
                    tool_calls=[{"name": "hidden", "status": "success"}],
                ),
                ChatMessage(
                    id=str(uuid4()),
                    session_id=session_id,
                    role="user",
                    content="general question",
                    sequence=3,
                    history_reliable=True,
                ),
                ChatMessage(
                    id=str(uuid4()),
                    session_id=session_id,
                    role="assistant",
                    content="general answer",
                    sequence=4,
                    history_reliable=True,
                ),
                ChatMessage(
                    id=str(uuid4()),
                    session_id=session_id,
                    role="user",
                    content="orphaned question",
                    sequence=5,
                    history_reliable=True,
                ),
            ]
        )
        session.commit()

        history, last_sequence = get_chat_history(session, session_id, pet_id=None)

    assert [(item.role, item.content) for item in history] == [
        ("user", "general question"),
        ("assistant", "general answer"),
    ]
    assert last_sequence == 5
