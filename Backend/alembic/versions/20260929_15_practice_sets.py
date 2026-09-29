"""Persist generated practice separately from official-paper results."""

import sqlalchemy as sa

from alembic import op

revision = "20260929_15"
down_revision = "20260926_14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("doubt_messages", sa.Column("practice_result", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("doubt_messages", "practice_result")
