"""Publish complete source-linked transcriptions without modifying student history."""

import re
import uuid
from urllib.parse import urlparse

import sqlalchemy as sa

NAMESPACE = uuid.UUID("7207de75-09b3-4b08-bf78-abe86f898c91")
COUNTS = {"english": 120, "general-knowledge": 120, "elementary-mathematics": 100}


def validate_paper(paper):
    slug, year, cycle = paper["subject_slug"], paper["year"], paper["cycle"]
    if slug not in COUNTS or type(year) is not int or not 2000 <= year <= 2100:
        raise ValueError("Invalid paper identity")
    if cycle not in {"I", "II"} or paper["question_count"] != COUNTS[slug]:
        raise ValueError("Invalid cycle or question count")
    source = urlparse(paper["source_url"])
    if (
        source.scheme != "https"
        or source.hostname not in {"upsc.gov.in", "www.upsc.gov.in"}
        or source.username
        or not source.path.lower().endswith(".pdf")
    ):
        raise ValueError("Non-official source URL")
    if not re.fullmatch(r"[a-f0-9]{64}", paper["source_checksum"]):
        raise ValueError("Missing source checksum")
    rows = paper["questions"]
    if [r["number"] for r in rows] != list(range(1, COUNTS[slug] + 1)):
        raise ValueError("A complete, ordered paper is required")
    seen = set()
    for row in rows:
        if row.get("complete") is not True or not isinstance(row.get("prompt"), str):
            raise ValueError("Incomplete question")
        if not 2 <= len(row["prompt"].strip()) <= 25000:
            raise ValueError("Invalid question text")
        options = row["options"]
        if not isinstance(options, list) or len(options) != 4:
            raise ValueError("Four choices are required")
        if any(not isinstance(o, str) or not o.strip() or len(o) > 12000 for o in options):
            raise ValueError("Invalid choice text")
        if len(set(options)) != 4:
            raise ValueError("Duplicate choices")
        identity = row["prompt"].strip(), tuple(options)
        if identity in seen:
            raise ValueError("Duplicate question content")
        seen.add(identity)
        page = row["page"]
        if type(page) is not int or not 1 <= page <= 100:
            raise ValueError("Invalid source page")
        asset = f"/papers/cds-{cycle.lower()}-{year}/{slug}/page-{page}.webp"
        if row["asset_url"] != asset:
            raise ValueError("Unexpected scan asset")
        if row["sourcePageUrl"] != f"{paper['source_url']}#page={page}":
            raise ValueError("Mismatched original source page")
        if row.get("text_reviewed") is not False:
            raise ValueError("Automated transcription must not claim human review")
        if row.get("source_compared") is not True:
            raise ValueError("Separate source-page comparison is required before publication")
        if any(key in row for key in ("correct_index", "is_verified", "explanation")):
            raise ValueError("Transcription must not manufacture answer keys")


def publish(connection, bundle):
    if bundle.get("version") != 1 or not bundle.get("papers"):
        raise ValueError("Invalid interactive archive bundle")
    metadata = sa.MetaData()
    papers = sa.Table("previous_papers", metadata, autoload_with=connection)
    questions = sa.Table("paper_questions", metadata, autoload_with=connection)
    subjects = sa.Table("subjects", metadata, autoload_with=connection)
    subjects_by_slug = dict(connection.execute(sa.select(subjects.c.slug, subjects.c.id)).all())
    existing_papers = {
        (p["year"], p["cycle"], p["subject_id"]): p
        for p in connection.execute(sa.select(papers)).mappings()
    }
    seen_papers, inserts, checksums = set(), [], []
    for entry in bundle["papers"]:
        validate_paper(entry)
        identity = entry["year"], entry["cycle"], subjects_by_slug[entry["subject_slug"]]
        if identity in seen_papers:
            raise ValueError("Duplicate paper in bundle")
        seen_papers.add(identity)
        paper = existing_papers.get(identity)
        if paper is None or paper["source_url"] != entry["source_url"]:
            raise ValueError("Paper is not in the official archive or source changed")
        if paper["official_question_count"] != entry["question_count"]:
            raise ValueError("Published paper question count differs")
        if paper["source_checksum"] and paper["source_checksum"] != entry["source_checksum"]:
            raise ValueError("Source checksum changed")
        existing = list(
            connection.execute(
                sa.select(questions).where(questions.c.paper_id == paper["id"])
            ).mappings()
        )
        if existing:
            # Idempotent only for this exact content; never replace a student's question.
            incoming = {r["number"]: r for r in entry["questions"]}
            if len(existing) != entry["question_count"] or any(
                q["number"] not in incoming
                or q["prompt"] != incoming[q["number"]]["prompt"]
                or q["options"] != incoming[q["number"]]["options"]
                for q in existing
            ):
                raise ValueError("Refusing to overwrite existing paper questions")
            continue
        for row in entry["questions"]:
            text = {
                key: row[key]
                for key in (
                    "prompt",
                    "options",
                    "sectionTitle",
                    "directions",
                    "passage",
                    "hasVisual",
                    "visualDescription",
                    "sourcePageUrl",
                    "text_reviewed",
                    "transcriptionSource",
                    "transcriptionVersion",
                )
            }
            inserts.append(
                {
                    "id": str(
                        uuid.uuid5(
                            NAMESPACE,
                            f"paper-question:{entry['year']}:{entry['cycle']}:{entry['subject_slug']}:{row['number']}",
                        )
                    ),
                    "paper_id": paper["id"],
                    "number": row["number"],
                    "topic_id": None,
                    "prompt": row["prompt"],
                    "context": row["passage"] or row["directions"] or None,
                    "options": row["options"],
                    "correct_index": 0,
                    "is_verified": False,
                    "explanation": "Answer verification pending.",
                    "source_label": f"Official UPSC CDS {entry['cycle']} {entry['year']} paper; "
                    "transcribed text, review pending",
                    "asset_url": row["asset_url"],
                    "transcription": text,
                }
            )
        checksums.append((paper["id"], entry["source_checksum"]))
    # Validate every paper before making any mutation. The caller owns the transaction.
    if inserts:
        connection.execute(questions.insert(), inserts)
    for paper_id, checksum in checksums:
        connection.execute(
            papers.update().where(papers.c.id == paper_id).values(source_checksum=checksum)
        )
    return len(checksums), len(inserts)
