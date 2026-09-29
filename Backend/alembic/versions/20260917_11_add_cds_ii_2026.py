"""Add all official CDS II 2026 papers and provisional Series A keys.

Revision ID: 20260917_11
Revises: 20260906_10
Create Date: 2026-09-17
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "20260917_11"
down_revision: str | None = "20260906_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAMESPACE = uuid.UUID("7207de75-09b3-4b08-bf78-abe86f898c91")


def stable_id(value: str) -> str:
    return str(uuid.uuid5(NAMESPACE, value))


SUBJECTS = {
    "english": ("English", 120, ["IMA", "INA", "AFA", "OTA"]),
    "general-knowledge": ("General Knowledge", 120, ["IMA", "INA", "AFA", "OTA"]),
    "elementary-mathematics": ("Elementary Mathematics", 100, ["IMA", "INA", "AFA"]),
}

PAPERS = {
    "english": (
        "https://www.upsc.gov.in/sites/default/files/QP-CDSE-II-26-ENGLISH-140926.pdf",
        "4093c1488b00f38cb59bb43cf644ef7ea202b9dacbe1474d31c04097810af68d",
        "https://www.upsc.gov.in/sites/default/files/ProvAnsKey-English-CDSE-II-26-16092026.pdf",
    ),
    "general-knowledge": (
        "https://www.upsc.gov.in/sites/default/files/QP-CDSE-II-26-GENERAL-KNOWLEDGE-140926.pdf",
        "27a42785cd72ce81264ecaeacbef1e85c0f111c215c7e57c443ade10af48ba8b",
        "https://www.upsc.gov.in/sites/default/files/ProvAnsKey-GK-CDSE-II-26-16092026.pdf",
    ),
    "elementary-mathematics": (
        "https://www.upsc.gov.in/sites/default/files/QP-CDSE-II-26-ELEMENTARY-MATHEMATICS-140926.pdf",
        "76ba727df62cc9ede113f44b9d032fe97059273f1102011a82b4d121e10fd557",
        "https://www.upsc.gov.in/sites/default/files/ProvAnsKey-ElMath-CDSE-II-26-16092026.pdf",
    ),
}

# Checked against the official UPSC Test Booklet Series A scans. Bilingual
# papers use only the English-language page from each English/Hindi pair.
PAGE_RANGES = {
    "english": [
        (2, 1, 4),
        (3, 5, 10),
        (4, 11, 18),
        (5, 19, 24),
        (6, 25, 30),
        (7, 31, 32),
        (8, 33, 34),
        (9, 35, 36),
        (10, 37, 38),
        (11, 39, 40),
        (12, 41, 50),
        (13, 51, 58),
        (14, 59, 66),
        (15, 67, 72),
        (16, 73, 80),
        (17, 81, 84),
        (18, 85, 88),
        (19, 89, 92),
        (20, 93, 98),
        (21, 99, 102),
        (22, 103, 106),
        (23, 107, 110),
        (24, 111, 113),
        (25, 114, 117),
        (26, 118, 120),
    ],
    "general-knowledge": [
        (3, 1, 4),
        (5, 5, 8),
        (7, 9, 11),
        (9, 12, 15),
        (11, 16, 19),
        (13, 20, 23),
        (15, 24, 26),
        (17, 27, 31),
        (19, 32, 35),
        (21, 36, 41),
        (23, 42, 46),
        (25, 47, 51),
        (27, 52, 56),
        (29, 57, 61),
        (31, 62, 67),
        (33, 68, 74),
        (35, 75, 80),
        (37, 81, 84),
        (39, 85, 89),
        (41, 90, 96),
        (43, 97, 101),
        (45, 102, 105),
        (47, 106, 110),
        (49, 111, 116),
        (51, 117, 120),
    ],
    "elementary-mathematics": [
        (3, 1, 6),
        (5, 7, 13),
        (7, 14, 20),
        (9, 21, 26),
        (11, 27, 33),
        (13, 34, 40),
        (15, 41, 46),
        (17, 47, 54),
        (19, 55, 60),
        (21, 61, 62),
        (23, 63, 64),
        (25, 65, 70),
        (27, 71, 77),
        (29, 78, 83),
        (31, 84, 90),
        (33, 91, 97),
        (35, 98, 100),
    ],
}

# X is the official provisional-key marker for the one dropped question.
ANSWER_KEYS = {
    "english": "ABDCAABCDABBADBCBACAACBDDABDAABDBACAABDABBBBBCDDABABDDCAABCDDBACBBCDCDBADABBDBBBCBDBDBBBCCDABCADCBADADCBABACDCCACCADCDAD",
    "general-knowledge": "CADBABCCBCAABCCACACACCDDDCABCCADCCBABBBBBBCCBCDABDBCCDCCCCBACABBADBBDCCBCADBCCBCACAXABBBBBBCBAACABCBBAACCCCDDBCADCADCDBC",
    "elementary-mathematics": "BAACCDCCBDDCCAACDBCCDDAABCDDBADAACCBCDAADCADCBBABCDBCBADBDBCDCDDBAACCBBABBABCCBBBBACCABCBDBCBCBADBDC",
}


def asset_for(slug: str, number: int) -> str:
    for page, first, last in PAGE_RANGES[slug]:
        if first <= number <= last:
            return f"/papers/cds-ii-2026/{slug}/page-{page}.webp"
    raise ValueError(f"No page mapped for {slug} question {number}")


def upgrade() -> None:
    paper_table = sa.table(
        "previous_papers",
        sa.column("id", sa.String()),
        sa.column("subject_id", sa.String()),
        sa.column("year", sa.Integer()),
        sa.column("cycle", sa.String()),
        sa.column("title", sa.String()),
        sa.column("exam_date", sa.Date()),
        sa.column("duration_seconds", sa.Integer()),
        sa.column("total_marks", sa.Integer()),
        sa.column("official_question_count", sa.Integer()),
        sa.column("negative_mark_fraction", sa.Float()),
        sa.column("academy_tracks", sa.JSON()),
        sa.column("source_url", sa.String()),
        sa.column("answer_key_url", sa.String()),
        sa.column("source_checksum", sa.String()),
        sa.column("is_published", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
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
    created_at = datetime(2026, 9, 17, tzinfo=UTC)

    for slug, (subject_name, count, tracks) in SUBJECTS.items():
        key = ANSWER_KEYS[slug]
        expected_dropped = 1 if slug == "general-knowledge" else 0
        if len(key) != count or set(key) - set("ABCDX") or key.count("X") != expected_dropped:
            raise ValueError(f"Invalid provisional answer key for {slug}")
        source_url, checksum, answer_key_url = PAPERS[slug]
        paper_id = stable_id(f"paper:2026:II:{slug}")
        op.bulk_insert(
            paper_table,
            [{
                "id": paper_id,
                "subject_id": stable_id(f"subject:{slug}"),
                "year": 2026,
                "cycle": "II",
                "title": f"CDS II 2026 - {subject_name}",
                "exam_date": date(2026, 9, 13),
                "duration_seconds": 7200,
                "total_marks": 100,
                "official_question_count": count,
                "negative_mark_fraction": 1 / 3,
                "academy_tracks": tracks,
                "source_url": source_url,
                "answer_key_url": answer_key_url,
                "source_checksum": checksum,
                "is_published": True,
                "created_at": created_at,
            }],
        )
        op.bulk_insert(
            question_table,
            [
                {
                    "id": stable_id(f"paper-question:2026:II:{slug}:{number}"),
                    "paper_id": paper_id,
                    "topic_id": None,
                    "number": number,
                    "prompt": f"Question {number} from the official UPSC CDS II 2026 paper",
                    "context": "Read the exact question and its options in the official scan below.",
                    "options": ["Option (a)", "Option (b)", "Option (c)", "Option (d)"],
                    "correct_index": 0 if letter == "X" else ord(letter) - ord("A"),
                    "explanation": (
                        "UPSC dropped this question from scoring in the provisional answer key."
                        if letter == "X"
                        else f"The provisional UPSC Series A answer key marks option ({letter.lower()})."
                    ),
                    "source_label": "Provisional UPSC CDS II 2026 Series A answer key (16 September 2026)",
                    "asset_url": asset_for(slug, number),
                    "is_verified": letter != "X",
                }
                for number, letter in enumerate(key, start=1)
            ],
        )


def downgrade() -> None:
    paper_table = sa.table("previous_papers", sa.column("id", sa.String()))
    ids = [stable_id(f"paper:2026:II:{slug}") for slug in SUBJECTS]
    op.get_bind().execute(sa.delete(paper_table).where(paper_table.c.id.in_(ids)))
