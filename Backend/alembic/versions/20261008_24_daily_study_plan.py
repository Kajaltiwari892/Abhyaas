"""Daily timetable, focus timer and topic-linked quiz targets."""

import sqlalchemy as sa

from alembic import op

revision = "20261008_24"
down_revision = "20261008_23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "study_preferences",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("daily_minutes", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(5), nullable=False),
        sa.Column("subject_slugs", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "daily_study_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("daily_minutes", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(5), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "plan_date", name="uq_study_plan_user_day"),
    )
    op.create_index("ix_daily_study_plans_user_id", "daily_study_plans", ["user_id"])
    op.create_index("ix_daily_study_plans_plan_date", "daily_study_plans", ["plan_date"])
    op.create_table(
        "daily_study_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "plan_id",
            sa.String(36),
            sa.ForeignKey("daily_study_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("subject_slug", sa.String(80), nullable=False),
        sa.Column("subject_name", sa.String(120), nullable=False),
        sa.Column("topic_slug", sa.String(80), nullable=False),
        sa.Column("topic_name", sa.String(120), nullable=False),
        sa.Column("reason", sa.String(24), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=False),
        sa.Column("study_minutes", sa.Integer(), nullable=False),
        sa.Column("quiz_minutes", sa.Integer(), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("study_elapsed_seconds", sa.Integer(), nullable=False),
        sa.Column("study_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("study_done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deferred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "quiz_attempt_id",
            sa.String(36),
            sa.ForeignKey("practice_attempts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("previous_quiz_answered", sa.Integer(), nullable=False),
        sa.Column("previous_quiz_correct", sa.Integer(), nullable=False),
        sa.UniqueConstraint("plan_id", "subject_slug"),
    )


def downgrade() -> None:
    op.drop_table("daily_study_tasks")
    op.drop_index("ix_daily_study_plans_plan_date", "daily_study_plans")
    op.drop_index("ix_daily_study_plans_user_id", "daily_study_plans")
    op.drop_table("daily_study_plans")
    op.drop_table("study_preferences")
