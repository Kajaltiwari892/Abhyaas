"""Add every official CDS I 2024 question to the paper archive.

Revision ID: 20260902_07
Revises: 20260901_06
Create Date: 2026-09-02
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260902_07"
down_revision: str | None = "20260901_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAMESPACE = uuid.UUID("7207de75-09b3-4b08-bf78-abe86f898c91")


def stable_id(value: str) -> str:
    return str(uuid.uuid5(NAMESPACE, value))


# Page ranges were checked against the official UPSC Test Booklet Series A scans.
# Bilingual papers use the English-language page from each English/Hindi pair.
PAGE_RANGES = {
    "english": [
        (2, 1, 5), (3, 6, 15), (4, 16, 20), (5, 21, 23), (6, 24, 27),
        (7, 28, 30), (8, 31, 33), (9, 34, 34), (10, 35, 36), (11, 37, 38),
        (12, 39, 40), (13, 41, 45), (14, 46, 50), (15, 51, 52),
        (16, 53, 55), (17, 56, 60), (18, 61, 70), (19, 71, 80),
        (20, 81, 85), (21, 86, 90), (22, 91, 94), (23, 95, 100),
        (24, 101, 102), (25, 103, 105), (26, 106, 110), (27, 111, 115),
        (28, 116, 120),
    ],
    "general-knowledge": [
        (3, 1, 5), (5, 6, 10), (7, 11, 16), (9, 17, 20), (11, 21, 26),
        (13, 27, 32), (15, 33, 40), (17, 41, 46), (19, 47, 51),
        (21, 52, 56), (23, 57, 60), (25, 61, 66), (27, 67, 71),
        (29, 72, 75), (31, 76, 80), (33, 81, 86), (35, 87, 94),
        (37, 95, 100), (39, 101, 104), (41, 105, 110), (43, 111, 116),
        (45, 117, 120),
    ],
    "elementary-mathematics": [
        (3, 1, 7), (5, 8, 14), (7, 15, 20), (9, 21, 27), (11, 28, 34),
        (13, 35, 40), (15, 41, 47), (17, 48, 54), (19, 55, 60),
        (21, 61, 67), (23, 68, 73), (25, 74, 78), (27, 79, 82),
        (29, 83, 87), (31, 88, 93), (33, 94, 97), (35, 98, 100),
    ],
}

INITIAL_VERIFIED = {
    "english": {16, 17, 18, 19, 20},
    "general-knowledge": {6, 9, 10},
    "elementary-mathematics": {8, 9, 10, 11, 12, 13, 14},
}


def asset_for(slug: str, number: int) -> str:
    for page, first, last in PAGE_RANGES[slug]:
        if first <= number <= last:
            return f"/papers/cds-i-2024/{slug}/page-{page}.webp"
    raise ValueError(f"No official scan page mapped for {slug} question {number}")


def upgrade() -> None:
    bind = op.get_bind()
    question_table = sa.table(
        "paper_questions",
        sa.column("id", sa.String()),
        sa.column("paper_id", sa.String()),
        sa.column("topic_id", sa.String()),
        sa.column("number", sa.Integer()),
        sa.column("prompt", sa.Text()),
        sa.column("context", sa.Text()),
        sa.column("options", sa.JSON()),
        sa.column("correct_index", sa.Integer()),
        sa.column("explanation", sa.Text()),
        sa.column("source_label", sa.String()),
        sa.column("asset_url", sa.String()),
        sa.column("is_verified", sa.Boolean()),
    )

    for slug, ranges in PAGE_RANGES.items():
        paper_id = stable_id(f"paper:2024:I:{slug}")
        count = max(last for _, _, last in ranges)
        existing = set(
            bind.execute(
                sa.select(question_table.c.number).where(question_table.c.paper_id == paper_id)
            ).scalars()
        )
        missing = []
        for number in range(1, count + 1):
            asset_url = asset_for(slug, number)
            if number in existing:
                bind.execute(
                    sa.update(question_table)
                    .where(
                        question_table.c.paper_id == paper_id,
                        question_table.c.number == number,
                    )
                    .values(asset_url=asset_url)
                )
                continue
            missing.append(
                {
                    "id": stable_id(f"paper-question:2024:I:{slug}:{number}"),
                    "paper_id": paper_id,
                    "topic_id": None,
                    "number": number,
                    "prompt": f"Question {number} from the official UPSC CDS I 2024 paper",
                    "context": "Read the exact question and its options in the official scan below.",
                    "options": ["Option (a)", "Option (b)", "Option (c)", "Option (d)"],
                    "correct_index": 0,
                    "explanation": "Answer verification pending.",
                    "source_label": "Official UPSC CDS I 2024 Test Booklet Series A scan",
                    "asset_url": asset_url,
                    "is_verified": False,
                }
            )
        if missing:
            op.bulk_insert(question_table, missing)


def downgrade() -> None:
    bind = op.get_bind()
    question_table = sa.table(
        "paper_questions",
        sa.column("id", sa.String()),
        sa.column("paper_id", sa.String()),
        sa.column("number", sa.Integer()),
        sa.column("asset_url", sa.String()),
        sa.column("is_verified", sa.Boolean()),
    )
    for slug in PAGE_RANGES:
        paper_id = stable_id(f"paper:2024:I:{slug}")
        generated_ids = [
            stable_id(f"paper-question:2024:I:{slug}:{number}")
            for number in range(1, max(last for _, _, last in PAGE_RANGES[slug]) + 1)
            if number not in INITIAL_VERIFIED[slug]
        ]
        bind.execute(sa.delete(question_table).where(question_table.c.id.in_(generated_ids)))
        bind.execute(
            sa.update(question_table)
            .where(question_table.c.paper_id == paper_id)
            .values(asset_url=None)
        )
