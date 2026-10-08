"""Keep generated practice private and distinct from the shared question bank.

Revision ID: 20261007_22
Revises: 20261007_21
"""

import sqlalchemy as sa

from alembic import op

revision = "20261007_22"
down_revision = "20261007_21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("questions") as batch:
        batch.add_column(sa.Column("owner_user_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_questions_owner_user_id",
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_index("ix_questions_owner_user_id", ["owner_user_id"])
    op.add_column(
        "practice_attempts",
        sa.Column("question_mode", sa.String(20), nullable=False, server_default="bank"),
    )


def downgrade() -> None:
    op.drop_column("practice_attempts", "question_mode")
    with op.batch_alter_table("questions") as batch:
        batch.drop_index("ix_questions_owner_user_id")
        batch.drop_constraint("fk_questions_owner_user_id", type_="foreignkey")
        batch.drop_column("owner_user_id")
