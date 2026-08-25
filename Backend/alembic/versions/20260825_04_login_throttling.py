"""Track failed login attempts for throttling.

Revision ID: 20260825_04
Revises: 20260825_03
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260825_04"
down_revision: str | None = "20260825_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email_digest", sa.String(length=64), nullable=False),
        sa.Column("ip_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_login_attempts_created_at"), "login_attempts", ["created_at"])
    op.create_index(op.f("ix_login_attempts_email_digest"), "login_attempts", ["email_digest"])
    op.create_index(op.f("ix_login_attempts_ip_digest"), "login_attempts", ["ip_digest"])


def downgrade() -> None:
    op.drop_index(op.f("ix_login_attempts_ip_digest"), table_name="login_attempts")
    op.drop_index(op.f("ix_login_attempts_email_digest"), table_name="login_attempts")
    op.drop_index(op.f("ix_login_attempts_created_at"), table_name="login_attempts")
    op.drop_table("login_attempts")
