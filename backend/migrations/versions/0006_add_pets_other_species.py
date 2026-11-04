"""Add pets.other_species.

Revision ID: 0006_add_pets_other_species
Revises: 0005_create_reminders
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_add_pets_other_species"
down_revision = "0005_create_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # P2-1：新增可空列，不收紧既有约束；存量宠物（包括 other）值均为 null。
    # SQLite 不强制 VARCHAR 长度，≤50 码点限制由应用层校验保证。
    op.add_column(
        "pets",
        sa.Column("other_species", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pets", "other_species")
