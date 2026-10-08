"""Persist personal revision sessions without changing original attempts.

Revision ID: 20261007_21
Revises: 20261005_20
"""

import sqlalchemy as sa

from alembic import op

revision = "20261007_21"
down_revision = "20261005_20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revision_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("current_position", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_revision_sessions_user_id", "revision_sessions", ["user_id"])
    op.create_index("ix_revision_sessions_status", "revision_sessions", ["status"])
    op.create_table(
        "revision_answers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("revision_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_key", sa.String(180), nullable=False),
        sa.Column("selected_index", sa.Integer(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("session_id", "question_key"),
    )
    op.create_index("ix_revision_answers_session_id", "revision_answers", ["session_id"])
    op.create_index("ix_revision_answers_question_key", "revision_answers", ["question_key"])


def downgrade() -> None:
    op.drop_table("revision_answers")
    op.drop_table("revision_sessions")
