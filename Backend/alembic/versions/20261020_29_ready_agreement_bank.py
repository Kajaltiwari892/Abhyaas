"""Publish checked agreement practice before students open a daily quiz."""

import json
from pathlib import Path

from alembic import op
from app.services.lesson_bank_publication import publish

revision = "20261020_29"
down_revision = "20261020_28"
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[2] / "data/lesson_banks/agreement_v1.json"
    publish(op.get_bind(), json.loads(path.read_text(encoding="utf-8")))


def downgrade():
    # Published questions can be referenced by student attempts; never delete them.
    pass
