"""Mark existing users verified while email verification is disabled.

Revision ID: 20260825_02
Revises: 20260821_01
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260825_02"
down_revision: str | None = "20260821_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    users = sa.table("users", sa.column("is_verified", sa.Boolean()))
    op.execute(users.update().where(users.c.is_verified.is_(False)).values(is_verified=True))


def downgrade() -> None:
    # This is an intentional data correction; previously verified users cannot be distinguished.
    pass
