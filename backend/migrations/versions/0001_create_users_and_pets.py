"""Create users and pets tables.

Revision ID: 0001_create_users_and_pets
Revises:
Create Date: 2026-11-02
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0001_create_users_and_pets"
down_revision = None
branch_labels = None
depends_on = None

DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("display_name", sa.String(length=50), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    bind.execute(
        sa.text(
            "INSERT INTO users (id, display_name, created_at) "
            "VALUES (:id, :display_name, :created_at) "
            "ON CONFLICT(id) DO NOTHING"
        ),
        {
            "id": DEFAULT_USER_ID,
            "display_name": "本地演示用户",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    if "pets" not in existing_tables:
        op.create_table(
            "pets",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(length=36),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("species", sa.String(length=10), nullable=False),
            sa.Column("breed", sa.String(length=100), nullable=True),
            sa.Column("birthday", sa.Date(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        return

    pet_columns = {column["name"] for column in inspect(bind).get_columns("pets")}
    if "user_id" not in pet_columns:
        with op.batch_alter_table("pets") as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.String(length=36), nullable=True))
            batch_op.create_foreign_key(
                "fk_pets_user_id_users", "users", ["user_id"], ["id"]
            )

    bind.execute(
        sa.text("UPDATE pets SET user_id = :user_id WHERE user_id IS NULL"),
        {"user_id": DEFAULT_USER_ID},
    )
    user_id_column = next(
        column
        for column in inspect(bind).get_columns("pets")
        if column["name"] == "user_id"
    )
    if user_id_column["nullable"]:
        with op.batch_alter_table("pets") as batch_op:
            batch_op.alter_column(
                "user_id",
                existing_type=sa.String(length=36),
                nullable=False,
            )


def downgrade() -> None:
    op.drop_table("pets")
    op.drop_table("users")
