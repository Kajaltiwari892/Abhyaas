"""Preserve set timing and provenance without changing existing attempt scores."""

import sqlalchemy as sa

from alembic import op

revision = "20260930_16"
down_revision = "20260929_15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("provenance", sa.JSON(), nullable=True))
    op.add_column(
        "practice_attempts",
        sa.Column("time_limit_seconds", sa.Integer(), nullable=False, server_default="1800"),
    )
    op.add_column(
        "practice_attempts",
        sa.Column("current_position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "practice_attempts",
        sa.Column("negative_mark_fraction", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("practice_attempts", "negative_mark_fraction")
    op.drop_column("practice_attempts", "current_position")
    op.drop_column("practice_attempts", "time_limit_seconds")
    op.drop_column("questions", "provenance")
