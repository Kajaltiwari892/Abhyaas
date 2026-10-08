"""Exam-aligned roadmap and account-owned daily check-in."""

import sqlalchemy as sa
from alembic import op

revision = "20261008_25"
down_revision = "20261008_24"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("study_preferences", sa.Column("exam_date", sa.Date(), nullable=True))
    op.add_column("study_preferences", sa.Column("plan_start_date", sa.Date(), nullable=True))
    op.add_column(
        "daily_study_plans", sa.Column("version", sa.Integer(), server_default="1", nullable=False)
    )
    op.add_column(
        "daily_study_plans", sa.Column("checkin_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("daily_study_tasks", sa.Column("curriculum_key", sa.String(100), nullable=True))
    op.add_column("daily_study_tasks", sa.Column("focus_points", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("daily_study_tasks", "focus_points")
    op.drop_column("daily_study_tasks", "curriculum_key")
    op.drop_column("daily_study_plans", "checkin_seen_at")
    op.drop_column("daily_study_plans", "version")
    op.drop_column("study_preferences", "plan_start_date")
    op.drop_column("study_preferences", "exam_date")
