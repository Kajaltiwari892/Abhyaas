"""Save checked practice answers separately from official paper keys.

Revision ID: 20261008_23
Revises: 20261007_22
"""

import sqlalchemy as sa

from alembic import op

revision = "20261008_23"
down_revision = "20261007_22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("paper_questions", sa.Column("answer_review", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("paper_questions", "answer_review")
