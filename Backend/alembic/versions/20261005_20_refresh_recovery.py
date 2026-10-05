"""Keep refresh-token lineage for bounded, idempotent renewal recovery.

Revision ID: 20261005_20
Revises: 20261003_19
"""
import sqlalchemy as sa

from alembic import op

revision = "20261005_20"
down_revision = "20261003_19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("refresh_sessions", sa.Column("family_id", sa.String(36), nullable=True))
    op.add_column("refresh_sessions", sa.Column("replacement_id", sa.String(36), nullable=True))
    # Existing sessions remain valid, with their original absolute expiration.
    op.execute("UPDATE refresh_sessions SET family_id = id WHERE family_id IS NULL")
    op.alter_column("refresh_sessions", "family_id", existing_type=sa.String(36), nullable=False)
    op.create_index("ix_refresh_sessions_family_id", "refresh_sessions", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_sessions_family_id", table_name="refresh_sessions")
    op.drop_column("refresh_sessions", "replacement_id")
    op.drop_column("refresh_sessions", "family_id")
