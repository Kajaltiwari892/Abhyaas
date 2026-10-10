"""Publish the first source-compared Sound and Waves collection; preserve history."""

import json
from pathlib import Path

from alembic import op
from app.services.chapter_publication import publish

revision = "20261009_26"
down_revision = "20261008_25"
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[2] / "data/chapter_questions/sound-waves-20261009.json"
    publish(op.get_bind(), json.loads(path.read_text(encoding="utf-8")))


def downgrade():
    # Questions can be referenced by saved attempts and chats. Never delete them.
    pass
