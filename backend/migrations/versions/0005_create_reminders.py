"""Create reminders.

Revision ID: 0005_create_reminders
Revises: 0004_create_records
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_create_reminders"
down_revision = "0004_create_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "pet_id",
            sa.String(length=36),
            sa.ForeignKey("pets.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column(
            "status", sa.String(length=10), nullable=False, server_default="pending"
        ),
        sa.Column(
            "source_record_id",
            sa.String(length=36),
            sa.ForeignKey("records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'cancelled')",
            name="ck_reminders_status",
        ),
    )
    op.create_index(
        "ix_reminders_user_pet_due", "reminders", ["user_id", "pet_id", "due_on"]
    )
    op.create_index("ix_reminders_user_due", "reminders", ["user_id", "due_on"])
    op.create_index("ix_reminders_source_record", "reminders", ["source_record_id"])


def downgrade() -> None:
    op.drop_index("ix_reminders_source_record", table_name="reminders")
    op.drop_index("ix_reminders_user_due", table_name="reminders")
    op.drop_index("ix_reminders_user_pet_due", table_name="reminders")
    op.drop_table("reminders")
