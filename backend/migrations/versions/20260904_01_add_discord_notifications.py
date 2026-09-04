"""Add durable Discord notification delivery state.

Revision ID: 20260904_01
Revises: 20260903_01
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_01"
down_revision: str | None = "20260903_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discord_notifications",
        sa.Column("marketplace", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["marketplace", "external_id"],
            ["listings.marketplace", "listings.external_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("marketplace", "external_id"),
    )
    op.create_index(
        "ix_discord_notifications_pending",
        "discord_notifications",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_discord_notifications_pending", table_name="discord_notifications"
    )
    op.drop_table("discord_notifications")
