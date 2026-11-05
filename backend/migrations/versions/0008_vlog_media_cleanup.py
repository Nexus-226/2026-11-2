"""Persist pending Vlog media cleanup."""

import sqlalchemy as sa
from alembic import op

revision = "0008_vlog_media_cleanup"
down_revision = "0007_create_vlogs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vlog_media_cleanup",
        sa.Column("storage_key", sa.String(length=80), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("vlog_media_cleanup")
