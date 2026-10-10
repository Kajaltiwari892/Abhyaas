"""Publish source-compared chapter PYQs into the existing shared paper tables.

Partial chapter collections are not complete papers. No answer keys, student data,
or existing question text are overwritten. All validation precedes database writes.
"""

import re
import uuid
from urllib.parse import urlparse

import sqlalchemy as sa

from app.services.question_bank import CHAPTERS, FOCUSES, classify_topics, text_checksum

NAMESPACE = uuid.UUID("7207de75-09b3-4b08-bf78-abe86f898c91")


def validate_bundle(bundle: dict) -> None:
    if bundle.get("version") != 1 or bundle.get("chapter") not in CHAPTERS:
        raise ValueError("Invalid chapter bundle")
    if not isinstance(bundle.get("papers"), list) or not bundle["papers"]:
        raise ValueError("Missing source papers")
    identities = set()
    for paper in bundle["papers"]:
        identity = paper["year"], paper["cycle"], paper["subject_slug"]
        if identity in identities:
            raise ValueError("Duplicate source paper")
        identities.add(identity)
        if type(paper["year"]) is not int or not 2000 <= paper["year"] <= 2100:
            raise ValueError("Invalid paper year")
        if paper["cycle"] not in {"I", "II"}:
            raise ValueError("Invalid CDS cycle")
        if paper["subject_slug"] != CHAPTERS[bundle["chapter"]][1]:
            raise ValueError("Wrong subject for chapter")
        source = urlparse(paper["source_url"])
        if (
            source.scheme != "https"
            or source.hostname not in {"upsc.gov.in", "www.upsc.gov.in"}
            or source.username
            or source.query
            or source.fragment
            or not source.path.lower().endswith(".pdf")
        ):
            raise ValueError("Non-official PDF source")
        if not re.fullmatch(r"[a-f0-9]{64}", paper["source_checksum"]):
            raise ValueError("Missing PDF checksum")
        numbers = set()
        if not paper.get("questions"):
            raise ValueError("Missing chapter questions")
        for question in paper["questions"]:
            number, page = question["number"], question["page"]
            if type(number) is not int or not 1 <= number <= 120 or number in numbers:
                raise ValueError("Invalid or duplicate question number")
            numbers.add(number)
            if type(page) is not int or not 1 <= page <= 100:
                raise ValueError("Invalid physical PDF page")
            if question.get("source_compared") is not True:
                raise ValueError("Source-page comparison required")
            if (
                not isinstance(question.get("review_note"), str)
                or not question["review_note"].strip()
            ):
                raise ValueError("Missing source review note")
            if (
                not isinstance(question.get("prompt"), str)
                or not 2 <= len(question["prompt"]) <= 25000
            ):
                raise ValueError("Invalid question text")
            options = question.get("options")
            if (
                not isinstance(options, list)
                or len(options) != 4
                or any(not isinstance(o, str) or not o.strip() or len(o) > 12000 for o in options)
            ):
                raise ValueError("Four complete options required")
            if len(set(options)) != 4:
                raise ValueError("Duplicate options")
            if any(k in question for k in ("correct_index", "is_verified", "answer_review")):
                raise ValueError("Chapter collection must not manufacture answer keys")
            if question.get("checksum") != text_checksum(question):
                raise ValueError("Question checksum differs from source review")
            if bundle["chapter"] not in classify_topics(question, paper["subject_slug"]):
                raise ValueError("Question does not match the chapter")


def publish(connection, bundle: dict, *, apply: bool = True) -> dict:
    validate_bundle(bundle)
    metadata = sa.MetaData()
    papers = sa.Table("previous_papers", metadata, autoload_with=connection)
    questions = sa.Table("paper_questions", metadata, autoload_with=connection)
    subjects = sa.Table("subjects", metadata, autoload_with=connection)
    subjects_by_slug = dict(connection.execute(sa.select(subjects.c.slug, subjects.c.id)).all())
    inserts, updates, source_updates = [], [], []
    for entry in bundle["papers"]:
        paper = (
            connection.execute(
                sa.select(papers).where(
                    papers.c.year == entry["year"],
                    papers.c.cycle == entry["cycle"],
                    papers.c.subject_id == subjects_by_slug.get(entry["subject_slug"], ""),
                )
            )
            .mappings()
            .one_or_none()
        )
        if not paper or paper["source_url"] != entry["source_url"]:
            raise ValueError("Source paper missing from the official archive or URL changed")
        if paper["source_checksum"] and paper["source_checksum"] != entry["source_checksum"]:
            raise ValueError("Original PDF checksum changed")
        existing = {
            q["number"]: q
            for q in connection.execute(
                sa.select(questions).where(questions.c.paper_id == paper["id"])
            ).mappings()
        }
        for row in entry["questions"]:
            if row["number"] > paper["official_question_count"]:
                raise ValueError("Question exceeds the official paper size")
            current = existing.get(row["number"])
            current_text = current["transcription"] if current else None
            if current_text and text_checksum(current_text) != row["checksum"]:
                raise ValueError("Existing question text differs; review rather than overwrite it")
            page = row["page"]
            directory = f"cds-{entry['cycle'].lower()}-{entry['year']}/{entry['subject_slug']}"
            asset = f"/papers/{directory}/page-{page}.webp"
            text = dict(
                current_text
                or {
                    k: row[k]
                    for k in (
                        "prompt",
                        "options",
                        "directions",
                        "passage",
                        "sectionTitle",
                        "hasVisual",
                    )
                    if k in row
                }
            )
            text.update(
                {
                    "sourcePageUrl": text.get("sourcePageUrl")
                    or f"{entry['source_url']}#page={page}",
                    "source_page": page,
                    "checksum": row["checksum"],
                    "text_reviewed": True,
                    "review_note": row["review_note"],
                    "topics": sorted(
                        set(text.get("topics", []))
                        | set(classify_topics(row, entry["subject_slug"]))
                    ),
                    "chapter_review": {
                        "chapter": bundle["chapter"],
                        "checksum": row["checksum"],
                        "method": "source-page-comparison",
                    },
                    "subtopics": sorted(
                        set(text.get("subtopics", []))
                        | {
                            slug
                            for slug, (_, parent, pattern) in FOCUSES.items()
                            if parent == bundle["chapter"]
                            and re.search(pattern, row["prompt"], re.I)
                        }
                    ),
                }
            )
            if current:
                if text != current_text:
                    updates.append((current["id"], text))
            else:
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
                        "context": row.get("passage") or row.get("directions") or None,
                        "options": row["options"],
                        "asset_url": asset,
                        "transcription": text,
                        "correct_index": 0,
                        "is_verified": False,
                        "explanation": "Answer verification pending.",
                        "source_label": (
                            f"Official UPSC CDS {entry['cycle']} {entry['year']} paper; "
                            "source-compared chapter question"
                        ),
                    }
                )
        if not paper["source_checksum"]:
            source_updates.append((paper["id"], entry["source_checksum"]))
    if apply:
        if inserts:
            connection.execute(questions.insert(), inserts)
        for question_id, text in updates:
            connection.execute(
                questions.update().where(questions.c.id == question_id).values(transcription=text)
            )
        for paper_id, checksum in source_updates:
            connection.execute(
                papers.update().where(papers.c.id == paper_id).values(source_checksum=checksum)
            )
    return {"created": len(inserts), "updated": len(updates), "sources": len(source_updates)}
