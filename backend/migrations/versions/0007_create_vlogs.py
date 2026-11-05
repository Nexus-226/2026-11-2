"""Create private pet vlog tables.

Revision ID: 0007_create_vlogs
Revises: 0006_add_pets_other_species
Create Date: 2026-11-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_create_vlogs"
down_revision = "0006_add_pets_other_species"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vlog_posts",
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
            nullable=False,
        ),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_vlog_posts_user_pet_occurred",
        "vlog_posts",
        ["user_id", "pet_id", "occurred_on"],
    )
    op.create_index(
        "ix_vlog_posts_user_occurred",
        "vlog_posts",
        ["user_id", "occurred_on"],
    )
    op.create_table(
        "vlog_media",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "vlog_id",
            sa.String(length=36),
            sa.ForeignKey("vlog_posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column("media_type", sa.String(length=10), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "media_type IN ('image', 'video')",
            name="ck_vlog_media_media_type",
        ),
        sa.UniqueConstraint("storage_key", name="uq_vlog_media_storage_key"),
    )
    op.create_index("ix_vlog_media_vlog", "vlog_media", ["vlog_id"])


def downgrade() -> None:
    op.drop_index("ix_vlog_media_vlog", table_name="vlog_media")
    op.drop_table("vlog_media")
    op.drop_index("ix_vlog_posts_user_occurred", table_name="vlog_posts")
    op.drop_index("ix_vlog_posts_user_pet_occurred", table_name="vlog_posts")
    op.drop_table("vlog_posts")
