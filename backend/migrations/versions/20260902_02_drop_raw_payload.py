"""Drop complete marketplace response payloads.

Revision ID: 20260902_02
Revises: 20260901_01
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260902_02"
down_revision: str | None = "20260901_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Delete raw payloads so only normalized listing fields remain."""
    op.drop_column("listings", "raw_payload")


def downgrade() -> None:
    """Restore an empty compatibility column; deleted payloads are not recoverable."""
    op.add_column(
        "listings",
        sa.Column(
            "raw_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("listings", "raw_payload", server_default=None)
