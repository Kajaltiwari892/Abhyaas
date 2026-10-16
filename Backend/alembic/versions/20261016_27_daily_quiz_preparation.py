"""Save quiz preparation between short, retryable serverless requests."""

import sqlalchemy as sa

from alembic import op

revision = "20261016_27"
down_revision = "20261009_26"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "daily_quiz_preparations",
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("daily_study_tasks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("bank_ids", sa.JSON(), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column(
            "attempt_id", sa.String(36), sa.ForeignKey("practice_attempts.id", ondelete="SET NULL")
        ),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("daily_quiz_preparations")
