"""Add all currently listed official CDS PDF papers, preserving interactive history."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import sqlalchemy as sa

from alembic import op

revision = "20261001_18"
down_revision = "20261001_17"
branch_labels = None
depends_on = None
NAMESPACE = uuid.UUID("7207de75-09b3-4b08-bf78-abe86f898c91")
SUBJECTS = {
    "english": ("English", 120, ["IMA", "INA", "AFA", "OTA"]),
    "general-knowledge": ("General Knowledge", 120, ["IMA", "INA", "AFA", "OTA"]),
    "elementary-mathematics": ("Elementary Mathematics", 100, ["IMA", "INA", "AFA"]),
}


def publish(connection, bundle):
    if bundle["version"] != 1:
        raise ValueError("Unsupported official archive version")
    metadata = sa.MetaData()
    subjects = sa.Table("subjects", metadata, autoload_with=connection)
    papers = sa.Table("previous_papers", metadata, autoload_with=connection)
    subject_ids = {
        slug: subject_id
        for slug, subject_id in connection.execute(sa.select(subjects.c.slug, subjects.c.id))
    }
    existing = list(connection.execute(sa.select(papers)).mappings())
    identities = {(p["year"], p["cycle"], p["subject_id"]) for p in existing}
    existing_ids = {p["id"] for p in existing}
    additions, seen = [], set()
    for row in bundle["papers"]:
        url = urlparse(row["source_url"])
        if (
            url.scheme != "https"
            or url.hostname not in {"upsc.gov.in", "www.upsc.gov.in"}
            or not url.path.lower().endswith(".pdf")
            or url.username
            or not row["pdf_checked"]
        ):
            raise ValueError("Unverified or non-official archive PDF")
        slug = row["subject_slug"]
        if slug not in SUBJECTS or slug not in subject_ids or row["cycle"] not in {"I", "II"}:
            raise ValueError("Invalid archive identity")
        year = row["year"]
        if not isinstance(year, int) or not 2000 <= year <= 2100:
            raise ValueError("Invalid archive year")
        identity = year, row["cycle"], subject_ids[slug]
        if identity in seen:
            raise ValueError("Duplicate archive identity")
        seen.add(identity)
        if identity in identities:
            continue  # Preserve IDs, source data, keys, questions and saved attempts.
        paper_id = str(uuid.uuid5(NAMESPACE, f"paper:{year}:{row['cycle']}:{slug}"))
        if paper_id in existing_ids:
            raise ValueError("Archive ID collision")
        name, question_count, academies = SUBJECTS[slug]
        additions.append(
            {
                "id": paper_id,
                "year": year,
                "cycle": row["cycle"],
                "subject_id": subject_ids[slug],
                "title": f"CDS {row['cycle']} {year} - {name}",
                "exam_date": None,
                "duration_seconds": 7200,
                "total_marks": 100,
                "official_question_count": question_count,
                "negative_mark_fraction": 1 / 3,
                "academy_tracks": academies,
                "source_url": row["source_url"],
                "answer_key_url": None,
                "source_checksum": None,
                "is_published": True,
                "created_at": datetime.fromisoformat(bundle["checked_at"]),
            }
        )
    if additions:
        connection.execute(papers.insert(), additions)
    return len(additions)


def upgrade():
    op.alter_column("previous_papers", "exam_date", existing_type=sa.Date(), nullable=True)
    path = Path(__file__).resolve().parents[2] / "data/upsc_paper_archive_20261001.json"
    added = publish(op.get_bind(), json.loads(path.read_text(encoding="utf-8")))
    print(f"Official PDF archive: added {added} papers; existing papers/history preserved")


def downgrade():
    # Papers may gain saved student attempts later. Never delete content on downgrade.
    pass
