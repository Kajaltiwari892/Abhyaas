"""Add private study profiles and persisted request limits.

Revision ID: 20260921_13
Revises: 20260921_12
"""

import sqlalchemy as sa

from alembic import op

revision = "20260921_13"
down_revision = "20260921_12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "doubt_study_profiles",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("explanation_style", sa.String(24), nullable=False),
        sa.Column("topic_counts", sa.JSON(), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("request_window_started", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requests_in_window", sa.Integer(), nullable=False),
        sa.Column("busy_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("doubt_study_profiles")
