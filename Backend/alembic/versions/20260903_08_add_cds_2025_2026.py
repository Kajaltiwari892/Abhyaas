"""Add the official CDS 2025 and available 2026 paper archives.

Revision ID: 20260903_08
Revises: 20260902_07
Create Date: 2026-09-03
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "20260903_08"
down_revision: str | None = "20260902_07"
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
    (2025, "I"): {
        "exam_date": date(2025, 4, 13),
        "folder": "cds-i-2025",
        "sources": {
            "english": (
                "https://www.upsc.gov.in/sites/default/files/QP-CDSE-I-25-ENGLISH-150425.pdf",
                "c5256ddd2db958b93d711a379910fd50be439b0d6daca8a8637b6cab640512f4",
            ),
            "general-knowledge": (
                "https://www.upsc.gov.in/sites/default/files/QP-CDSE-I-25-GENERAL-KNOWLEDGE-150425.pdf",
                "a5a03b51e31210ef8abab78512b5ed6f40bf9d0206d8f8c89322b9b7107b8e83",
            ),
            "elementary-mathematics": (
                "https://www.upsc.gov.in/sites/default/files/QP-CDSE-I-25-ELEMENTARY-MATHEMATICS-150425.pdf",
                "f6d829f6421ccc8ac0b822cb240f9a5657c7449576283fc74bd98905d5c32983",
            ),
        },
    },
    (2025, "II"): {
        "exam_date": date(2025, 9, 14),
        "folder": "cds-ii-2025",
        "sources": {
            "english": (
                "https://www.upsc.gov.in/sites/default/files/QP-CDSE-II-25-ENGLISH-150925.pdf",
                "8ee0501f6b9cdeed191e9ac8c4a8e97761b2e6ca4c3a98068e2ae37f0b8b8228",
            ),
            "general-knowledge": (
                "https://www.upsc.gov.in/sites/default/files/QP-CDSE-II-25-GENERAL-KNOWLEDGE-150925.pdf",
                "829d0be0dfb31d59113e2a51e08a6dc134bb92b877a34d398c9926f297f7c88b",
            ),
            "elementary-mathematics": (
                "https://www.upsc.gov.in/sites/default/files/QP-CDSE-II-25-ELEMENTARY-MATHEMATICS-150925.pdf",
                "0a3654c25177fbd18e9c9dfe2d123d497881147a02edf70f9acf14133b2246b3",
            ),
        },
    },
    (2026, "I"): {
        "exam_date": date(2026, 4, 12),
        "folder": "cds-i-2026",
        "sources": {
            "english": (
                "https://www.upsc.gov.in/sites/default/files/QP-CDS-I-26-ENGLISH-130426.pdf",
                "448a3c97245b5c9a2b84bf6ccf118aea295726460d96ca3512c8dd90ab294d51",
            ),
            "general-knowledge": (
                "https://www.upsc.gov.in/sites/default/files/QP-CDS-I-26-GENERAL-KNOWLEDGE-130426.pdf",
                "6671f97485021a43c6d1e194cd02663e873b4aacf989a7478d9d43faa6723628",
            ),
            "elementary-mathematics": (
                "https://www.upsc.gov.in/sites/default/files/QP-CDS-I-26-ELEMENTARY-MATHEMATICS-130426.pdf",
                "ff73f9185d1eb7d4da64e67f0c4f6ed77ce07298994ab260ee7dcea747a5d9fb",
            ),
        },
    },
}

# Page ranges were checked against the official UPSC Test Booklet Series A scans.
# For bilingual papers, only the English-language page from each English/Hindi pair is shown.
PAGE_RANGES = {
    (2025, "I", "english"): [
        (2, 1, 8),
        (3, 9, 14),
        (4, 15, 20),
        (5, 21, 26),
        (6, 27, 30),
        (7, 31, 37),
        (8, 38, 43),
        (9, 44, 48),
        (10, 49, 55),
        (11, 56, 57),
        (12, 58, 60),
        (13, 61, 62),
        (14, 63, 64),
        (15, 65, 67),
        (16, 68, 70),
        (17, 71, 73),
        (18, 74, 77),
        (19, 78, 79),
        (20, 80, 82),
        (21, 83, 87),
        (22, 88, 91),
        (23, 92, 95),
        (24, 96, 100),
        (25, 101, 104),
        (26, 105, 108),
        (27, 109, 113),
        (28, 114, 120),
    ],
    (2025, "I", "general-knowledge"): [
        (3, 1, 6),
        (5, 7, 13),
        (7, 14, 20),
        (9, 21, 26),
        (11, 27, 34),
        (13, 35, 41),
        (15, 42, 46),
        (17, 47, 55),
        (19, 56, 63),
        (21, 64, 70),
        (23, 71, 80),
        (25, 81, 86),
        (27, 87, 91),
        (29, 92, 97),
        (31, 98, 105),
        (33, 106, 112),
        (35, 113, 120),
    ],
    (2025, "I", "elementary-mathematics"): [
        (3, 1, 10),
        (5, 11, 20),
        (7, 21, 27),
        (9, 28, 35),
        (11, 36, 44),
        (13, 45, 50),
        (15, 51, 58),
        (17, 59, 64),
        (19, 65, 70),
        (21, 71, 80),
        (23, 81, 90),
        (25, 91, 95),
        (27, 96, 100),
    ],
    (2025, "II", "english"): [
        (2, 1, 10),
        (3, 11, 15),
        (4, 16, 20),
        (5, 21, 27),
        (6, 28, 34),
        (7, 35, 40),
        (8, 41, 46),
        (9, 47, 50),
        (10, 51, 55),
        (11, 56, 60),
        (12, 61, 62),
        (13, 63, 65),
        (14, 66, 67),
        (15, 68, 70),
        (16, 71, 75),
        (17, 76, 80),
        (18, 81, 90),
        (19, 91, 94),
        (20, 95, 100),
        (21, 101, 105),
        (22, 106, 110),
        (23, 111, 116),
        (24, 117, 120),
    ],
    (2025, "II", "general-knowledge"): [
        (3, 1, 4),
        (5, 5, 10),
        (7, 11, 17),
        (9, 18, 25),
        (11, 26, 34),
        (13, 35, 42),
        (15, 43, 50),
        (17, 51, 55),
        (19, 56, 60),
        (21, 61, 66),
        (23, 67, 73),
        (25, 74, 78),
        (27, 79, 84),
        (29, 85, 89),
        (31, 90, 93),
        (33, 94, 97),
        (35, 98, 102),
        (37, 103, 107),
        (39, 108, 112),
        (41, 113, 116),
        (43, 117, 120),
    ],
    (2025, "II", "elementary-mathematics"): [
        (3, 1, 7),
        (5, 8, 13),
        (7, 14, 19),
        (9, 20, 25),
        (11, 26, 31),
        (13, 32, 37),
        (15, 38, 41),
        (17, 42, 47),
        (19, 48, 53),
        (21, 54, 59),
        (23, 60, 65),
        (25, 66, 70),
        (27, 71, 76),
        (29, 77, 80),
        (31, 81, 82),
        (33, 83, 84),
        (35, 85, 86),
        (37, 87, 88),
        (39, 89, 90),
        (41, 91, 96),
        (43, 97, 100),
    ],
    (2026, "I", "english"): [
        (2, 1, 6),
        (3, 7, 15),
        (4, 16, 24),
        (5, 25, 31),
        (6, 32, 35),
        (7, 36, 39),
        (8, 40, 45),
        (9, 46, 55),
        (10, 56, 65),
        (11, 66, 75),
        (12, 76, 82),
        (13, 83, 86),
        (14, 87, 90),
        (15, 91, 97),
        (16, 98, 102),
        (17, 103, 105),
        (18, 106, 109),
        (19, 110, 115),
        (20, 116, 120),
    ],
    (2026, "I", "general-knowledge"): [
        (3, 1, 8),
        (5, 9, 14),
        (7, 15, 20),
        (9, 21, 25),
        (11, 26, 30),
        (13, 31, 37),
        (15, 38, 42),
        (17, 43, 48),
        (19, 49, 55),
        (21, 56, 61),
        (23, 62, 68),
        (25, 69, 72),
        (27, 73, 76),
        (29, 77, 83),
        (31, 84, 87),
        (33, 88, 92),
        (35, 93, 97),
        (37, 98, 102),
        (39, 103, 107),
        (41, 108, 112),
        (43, 113, 120),
    ],
    (2026, "I", "elementary-mathematics"): [
        (3, 1, 6),
        (5, 7, 11),
        (7, 12, 16),
        (9, 17, 21),
        (11, 22, 27),
        (13, 28, 33),
        (15, 34, 38),
        (17, 39, 44),
        (19, 45, 49),
        (21, 50, 55),
        (23, 56, 59),
        (25, 60, 64),
        (27, 65, 69),
        (29, 70, 72),
        (31, 73, 74),
        (33, 75, 76),
        (35, 77, 78),
        (37, 79, 81),
        (39, 82, 88),
        (41, 89, 94),
        (43, 95, 100),
    ],
}


def asset_for(year: int, cycle: str, slug: str, number: int) -> str:
    folder = PAPERS[(year, cycle)]["folder"]
    for page, first, last in PAGE_RANGES[(year, cycle, slug)]:
        if first <= number <= last:
            return f"/papers/{folder}/{slug}/page-{page}.webp"
    raise ValueError(f"No page mapped for {year} {cycle} {slug} question {number}")


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
    created_at = datetime(2026, 9, 3, tzinfo=UTC)

    for (year, cycle), paper in PAPERS.items():
        for slug, (subject_name, count, tracks) in SUBJECTS.items():
            source_url, checksum = paper["sources"][slug]
            paper_id = stable_id(f"paper:{year}:{cycle}:{slug}")
            op.bulk_insert(
                paper_table,
                [
                    {
                        "id": paper_id,
                        "subject_id": stable_id(f"subject:{slug}"),
                        "year": year,
                        "cycle": cycle,
                        "title": f"CDS {cycle} {year} - {subject_name}",
                        "exam_date": paper["exam_date"],
                        "duration_seconds": 7200,
                        "total_marks": 100,
                        "official_question_count": count,
                        "negative_mark_fraction": 1 / 3,
                        "academy_tracks": tracks,
                        "source_url": source_url,
                        "answer_key_url": None,
                        "source_checksum": checksum,
                        "is_published": True,
                        "created_at": created_at,
                    }
                ],
            )
            op.bulk_insert(
                question_table,
                [
                    {
                        "id": stable_id(f"paper-question:{year}:{cycle}:{slug}:{number}"),
                        "paper_id": paper_id,
                        "topic_id": None,
                        "number": number,
                        "prompt": (
                            f"Question {number} from the official UPSC CDS {cycle} {year} paper"
                        ),
                        "context": (
                            "Read the exact question and its options in the official scan below."
                        ),
                        "options": ["Option (a)", "Option (b)", "Option (c)", "Option (d)"],
                        "correct_index": 0,
                        "explanation": "Answer verification pending.",
                        "source_label": (
                            f"Official UPSC CDS {cycle} {year} Test Booklet Series A scan"
                        ),
                        "asset_url": asset_for(year, cycle, slug, number),
                        "is_verified": False,
                    }
                    for number in range(1, count + 1)
                ],
            )


def downgrade() -> None:
    paper_table = sa.table("previous_papers", sa.column("id", sa.String()))
    ids = [stable_id(f"paper:{year}:{cycle}:{slug}") for year, cycle in PAPERS for slug in SUBJECTS]
    op.get_bind().execute(sa.delete(paper_table).where(paper_table.c.id.in_(ids)))
