"""Save an optional academy target without changing student history."""

import sqlalchemy as sa

from alembic import op

revision = "20261003_19"
down_revision = "20261001_18"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "target_academy",
            sa.String(3),
            sa.CheckConstraint(
                "target_academy IN ('ima', 'ina', 'afa', 'ota')",
                name="ck_users_target_academy",
            ),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("users", "target_academy")
