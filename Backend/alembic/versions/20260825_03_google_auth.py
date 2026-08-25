"""Support passwordless Google identities.

Revision ID: 20260825_03
Revises: 20260825_02
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260825_03"
down_revision: str | None = "20260825_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)
    op.add_column("users", sa.Column("google_sub", sa.String(255), nullable=True))
    op.create_index(op.f("ix_users_google_sub"), "users", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_google_sub"), table_name="users")
    op.drop_column("users", "google_sub")
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
