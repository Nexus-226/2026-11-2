from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.repositories.chats import get_chat_history


def test_migration_backfills_multiple_sessions_and_marks_legacy_unreliable(
    tmp_path: Path,
) -> None:
    database_url = URL.create("sqlite", database=str(tmp_path / "legacy_chat.db"))
    alembic_config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    alembic_config.set_main_option(
        "sqlalchemy.url",
        database_url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    command.upgrade(alembic_config, "0002_create_chat_tables")

    engine = create_engine(database_url)
    timestamp = "2026-11-03 12:00:00"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO chat_sessions "
                "(id, user_id, created_at, updated_at) VALUES "
                "('session-a', '00000000-0000-0000-0000-000000000001', "
                ":timestamp, :timestamp), "
                "('session-b', '00000000-0000-0000-0000-000000000001', "
                ":timestamp, :timestamp)"
            ),
            {"timestamp": timestamp},
        )
        connection.execute(
            text(
                "INSERT INTO chat_messages "
                "(id, session_id, role, content, created_at) VALUES "
                "('a-user', 'session-a', 'user', 'a question', :timestamp), "
                "('b-user', 'session-b', 'user', 'b question', :timestamp), "
                "('a-assistant', 'session-a', 'assistant', 'a answer', :timestamp), "
                "('b-assistant', 'session-b', 'assistant', 'b answer', :timestamp)"
            ),
            {"timestamp": timestamp},
        )

    command.upgrade(alembic_config, "head")

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, session_id, role, sequence, history_reliable "
                "FROM chat_messages ORDER BY session_id, sequence"
            )
        ).all()
        constraint_rows = connection.execute(
            text(
                "SELECT COUNT(*) FROM chat_messages "
                "WHERE sequence IS NULL OR history_reliable IS NULL"
            )
        ).scalar_one()

    assert [(row.id, row.sequence) for row in rows] == [
        ("a-user", 1),
        ("a-assistant", 2),
        ("b-user", 1),
        ("b-assistant", 2),
    ]
    assert all(not row.history_reliable for row in rows)
    assert constraint_rows == 0
    with Session(engine) as session:
        history, _ = get_chat_history(session, "session-a", pet_id=None)
    assert history == []

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO chat_messages "
                "(id, session_id, role, content, sequence, "
                "history_reliable, created_at) VALUES "
                "('duplicate-sequence', 'session-a', 'user', 'duplicate', "
                "1, 0, :timestamp)"
            ),
            {"timestamp": timestamp},
        )
    engine.dispose()
