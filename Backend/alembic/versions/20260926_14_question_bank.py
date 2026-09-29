"""Shared source-linked question text and structured PYQ conversation results."""

import sqlalchemy as sa

from alembic import op

revision = "20260926_14"
down_revision = "20260921_13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("paper_questions", sa.Column("transcription", sa.JSON(), nullable=True))
    op.add_column("doubt_messages", sa.Column("pyq_result", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("doubt_messages", "pyq_result")
    op.drop_column("paper_questions", "transcription")
