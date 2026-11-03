"""Add ordered chat history and mark legacy messages as unverified.

Revision ID: 0003_chat_message_history
Revises: 0002_create_chat_tables
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0003_chat_message_history"
down_revision = "0002_create_chat_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("sequence", sa.Integer(), nullable=True),
    )
    op.add_column(
        "chat_messages",
        sa.Column(
            "history_reliable",
            sa.Boolean(),
            nullable=True,
            server_default=sa.false(),
        ),
    )

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        rows = bind.execute(
            text(
                "SELECT id, session_id FROM chat_messages "
                "ORDER BY session_id, created_at, rowid"
            )
        )
    else:
        rows = bind.execute(
            text(
                "SELECT id, session_id FROM chat_messages "
                "ORDER BY session_id, created_at, id"
            )
        )

    next_sequences: dict[str, int] = {}
    for row in rows:
        sequence = next_sequences.get(row.session_id, 0) + 1
        next_sequences[row.session_id] = sequence
        bind.execute(
            text(
                "UPDATE chat_messages SET sequence = :sequence, "
                "history_reliable = :history_reliable WHERE id = :id"
            ),
            {"id": row.id, "sequence": sequence, "history_reliable": False},
        )

    # No existing database was available to verify that its legacy row order
    # can be replayed safely; retain those rows but exclude them from model input.
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.alter_column(
            "sequence",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.alter_column(
            "history_reliable",
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        )
        batch_op.create_unique_constraint(
            "uq_chat_messages_session_sequence", ["session_id", "sequence"]
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.drop_constraint("uq_chat_messages_session_sequence", type_="unique")
        batch_op.drop_column("history_reliable")
        batch_op.drop_column("sequence")
