"""Point CDS I 2026 English question 109 at the page where it begins.

Revision ID: 20260906_10
Revises: 20260906_09
Create Date: 2026-09-06
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260906_10"
down_revision: str | None = "20260906_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAMESPACE = uuid.UUID("7207de75-09b3-4b08-bf78-abe86f898c91")


def question_id(number: int) -> str:
    return str(uuid.uuid5(NAMESPACE, f"paper-question:2026:I:english:{number}"))


def upgrade() -> None:
    questions = sa.table(
        "paper_questions", sa.column("id", sa.String()), sa.column("asset_url", sa.String())
    )
    op.get_bind().execute(
        questions.update()
        .where(questions.c.id == question_id(109))
        .values(asset_url="/papers/cds-i-2026/english/page-19.webp")
    )


def downgrade() -> None:
    questions = sa.table(
        "paper_questions", sa.column("id", sa.String()), sa.column("asset_url", sa.String())
    )
    op.get_bind().execute(
        questions.update()
        .where(questions.c.id == question_id(109))
        .values(asset_url="/papers/cds-i-2026/english/page-18.webp")
    )
