"""Persist generated candidates separately from independently checked questions."""

import sqlalchemy as sa

from alembic import op

revision = "20261020_28"
down_revision = "20261016_27"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "daily_quiz_preparations",
        sa.Column("pending_questions", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "daily_quiz_preparations",
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "daily_quiz_preparations", sa.Column("next_retry_at", sa.DateTime(timezone=True))
    )


def downgrade():
    op.drop_column("daily_quiz_preparations", "next_retry_at")
    op.drop_column("daily_quiz_preparations", "failure_count")
    op.drop_column("daily_quiz_preparations", "pending_questions")
