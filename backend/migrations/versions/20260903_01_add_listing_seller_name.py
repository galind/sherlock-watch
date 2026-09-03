"""Add seller name to listings.

Revision ID: 20260903_01
Revises: 20260902_01
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_01"
down_revision: str | None = "20260902_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("seller_name", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("listings", "seller_name")
