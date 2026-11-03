"""Create daily care records.

Revision ID: 0004_create_records
Revises: 0003_chat_message_history
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_create_records"
down_revision = "0003_chat_message_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "records",
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
        sa.Column("record_type", sa.String(length=20), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("weight_kg", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "record_type IN ('vaccine', 'deworming', 'bath', 'weight')",
            name="ck_records_record_type",
        ),
        sa.CheckConstraint(
            "(record_type = 'weight' AND weight_kg IS NOT NULL "
            "AND weight_kg > 0 AND weight_kg <= 500) "
            "OR (record_type != 'weight' AND weight_kg IS NULL)",
            name="ck_records_weight_by_type",
        ),
    )
    op.create_index(
        "ix_records_user_pet_occurred",
        "records",
        ["user_id", "pet_id", "occurred_on"],
    )
    op.create_index(
        "ix_records_user_occurred",
        "records",
        ["user_id", "occurred_on"],
    )


def downgrade() -> None:
    op.drop_index("ix_records_user_occurred", table_name="records")
    op.drop_index("ix_records_user_pet_occurred", table_name="records")
    op.drop_table("records")
