"""Make complete paper attempts interactive and add the official CDS II 2025 key.

Revision ID: 20260906_09
Revises: 20260903_08
Create Date: 2026-09-06
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260906_09"
down_revision: str | None = "20260903_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAMESPACE = uuid.UUID("7207de75-09b3-4b08-bf78-abe86f898c91")
ANSWER_KEY_URLS = {
    "english": "https://www.upsc.gov.in/sites/default/files/AnsKey-CDS-II-Examination-2025-ENGLISH-130826.pdf",
    "general-knowledge": "https://www.upsc.gov.in/sites/default/files/AnsKey-CDS-II-Examination-2025-GK-130826.pdf",
    "elementary-mathematics": "https://www.upsc.gov.in/sites/default/files/AnsKey-CDS-II-Examination-2025-ElemMath-130826.pdf",
}
ANSWER_KEYS = {
    "english": "".join((
        "DBCAABCDAB", "BCCCDCBDCD", "BBCCDBCADA", "CDCDBBDCCA",
        "DACAACABAD", "ACCDCBDBAA", "CBDCCBCCAD", "CCBCBDAACB",
        "BCBADACBBB", "ACABDBBBCB", "CACCACDACB", "ADBABABAAD",
    )),
    "general-knowledge": "".join((
        "CACDDBCBBC", "BBABCACBCA", "CBBCBCDDBA", "DDBCDCDCBD",
        "DABCCABCCC", "BADAABCDBD", "ACBCCADADB", "CDAABABACA",
        "BBBDDCCBCD", "BADCDCCCCC", "BDCDCBABCA", "BDDCCCBDAA",
    )),
    "elementary-mathematics": "".join((
        "CDAAAABAAC", "ACBCACBBAC", "AACDBBACDD", "DCAADCCCCB",
        "CDCBACBABB", "BCCABCACAD", "CDCBDCDBCD", "ACDCCCACDD",
        "DACDDBDBAD", "DCDBABCCCD",
    )),
}


def stable_id(value: str) -> str:
    return str(uuid.uuid5(NAMESPACE, value))


def upgrade() -> None:
    op.add_column(
        "paper_attempts",
        sa.Column("scored_questions", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        "UPDATE paper_attempts SET scored_questions = total_questions "
        "WHERE status = 'completed'"
    )

    bind = op.get_bind()
    papers = sa.table(
        "previous_papers", sa.column("id", sa.String()), sa.column("answer_key_url", sa.String())
    )
    questions = sa.table(
        "paper_questions",
        sa.column("id", sa.String()),
        sa.column("correct_index", sa.Integer()),
        sa.column("explanation", sa.Text()),
        sa.column("source_label", sa.String()),
        sa.column("is_verified", sa.Boolean()),
    )
    for slug, key in ANSWER_KEYS.items():
        expected = 100 if slug == "elementary-mathematics" else 120
        if len(key) != expected or set(key) - set("ABCD"):
            raise ValueError(f"Invalid official answer key for {slug}")
        bind.execute(
            papers.update().where(papers.c.id == stable_id(f"paper:2025:II:{slug}")).values(
                answer_key_url=ANSWER_KEY_URLS[slug]
            )
        )
        for number, letter in enumerate(key, start=1):
            bind.execute(
                questions.update()
                .where(questions.c.id == stable_id(f"paper-question:2025:II:{slug}:{number}"))
                .values(
                    correct_index=ord(letter) - ord("A"),
                    explanation=(
                        f"The official UPSC Series A answer key marks option ({letter.lower()})."
                    ),
                    source_label="Official UPSC CDS II 2025 Series A answer key (13 August 2026)",
                    is_verified=True,
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    papers = sa.table(
        "previous_papers", sa.column("id", sa.String()), sa.column("answer_key_url", sa.String())
    )
    questions = sa.table(
        "paper_questions",
        sa.column("id", sa.String()),
        sa.column("correct_index", sa.Integer()),
        sa.column("explanation", sa.Text()),
        sa.column("source_label", sa.String()),
        sa.column("is_verified", sa.Boolean()),
    )
    for slug, key in ANSWER_KEYS.items():
        bind.execute(
            papers.update().where(papers.c.id == stable_id(f"paper:2025:II:{slug}")).values(
                answer_key_url=None
            )
        )
        for number in range(1, len(key) + 1):
            bind.execute(
                questions.update()
                .where(questions.c.id == stable_id(f"paper-question:2025:II:{slug}:{number}"))
                .values(
                    correct_index=0,
                    explanation="Answer verification pending.",
                    source_label=(
                        "Official UPSC Test Booklet Series A scan; answer verification pending"
                    ),
                    is_verified=False,
                )
            )
    op.drop_column("paper_attempts", "scored_questions")
