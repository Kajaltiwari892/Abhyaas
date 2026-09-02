"""Import a human-reviewed previous-paper JSON file.

Run from Backend with:
    .\.venv\Scripts\python.exe .\scripts\import_papers.py .\data\papers\paper-template.json

The importer is idempotent: it updates the paper and each question identified by
year, cycle, subject slug, and question number.
"""

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.papers import PaperQuestion, PreviousPaper
from app.models.practice import Subject, Topic


def read_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "year",
        "cycle",
        "subject_slug",
        "title",
        "exam_date",
        "official_question_count",
        "source_url",
        "questions",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    if payload["cycle"] not in {"I", "II"}:
        raise ValueError("cycle must be I or II")
    return payload


def validate_question(question: dict[str, Any]) -> None:
    required = {"number", "prompt", "options"}
    missing = sorted(required - question.keys())
    if missing:
        raise ValueError(f"Question {question.get('number', '?')} is missing: {', '.join(missing)}")
    options = question["options"]
    correct_index = question.get("correct_index")
    if not isinstance(options, list) or len(options) < 2:
        raise ValueError(f"Question {question['number']} needs at least two options")
    if question.get("is_verified") is True and (
        not isinstance(correct_index, int) or not 0 <= correct_index < len(options)
    ):
        raise ValueError(f"Question {question['number']} has an invalid correct_index")


async def import_payload(payload: dict[str, Any]) -> tuple[int, int]:
    async with SessionLocal() as db:
        subject = (
            await db.execute(
                select(Subject)
                .options(selectinload(Subject.topics))
                .where(Subject.slug == payload["subject_slug"])
            )
        ).scalar_one_or_none()
        if subject is None:
            raise ValueError(f"Unknown subject slug: {payload['subject_slug']}")
        topics: dict[str, Topic] = {topic.slug: topic for topic in subject.topics}

        paper = (
            await db.execute(
                select(PreviousPaper).where(
                    PreviousPaper.year == int(payload["year"]),
                    PreviousPaper.cycle == payload["cycle"],
                    PreviousPaper.subject_id == subject.id,
                )
            )
        ).scalar_one_or_none()
        if paper is None:
            paper = PreviousPaper(
                year=int(payload["year"]),
                cycle=payload["cycle"],
                subject_id=subject.id,
            )
            db.add(paper)

        paper.title = payload["title"].strip()
        paper.exam_date = date.fromisoformat(payload["exam_date"])
        paper.duration_seconds = int(payload.get("duration_seconds", 7200))
        paper.total_marks = int(payload.get("total_marks", 100))
        paper.official_question_count = int(payload["official_question_count"])
        paper.negative_mark_fraction = float(payload.get("negative_mark_fraction", 1 / 3))
        paper.academy_tracks = list(payload.get("academy_tracks", []))
        paper.source_url = payload["source_url"].strip()
        paper.answer_key_url = payload.get("answer_key_url") or None
        paper.source_checksum = payload.get("source_checksum") or None
        paper.is_published = bool(payload.get("is_published", True))
        await db.flush()

        created = 0
        updated = 0
        for item in payload["questions"]:
            validate_question(item)
            topic_slug = item.get("topic_slug")
            if topic_slug and topic_slug not in topics:
                raise ValueError(f"Unknown topic slug: {topic_slug}")
            question = (
                await db.execute(
                    select(PaperQuestion).where(
                        PaperQuestion.paper_id == paper.id,
                        PaperQuestion.number == int(item["number"]),
                    )
                )
            ).scalar_one_or_none()
            if question is None:
                question = PaperQuestion(paper_id=paper.id, number=int(item["number"]))
                db.add(question)
                created += 1
            else:
                updated += 1
            question.topic_id = topics[topic_slug].id if topic_slug else None
            question.prompt = item["prompt"].strip()
            question.context = item.get("context") or None
            question.options = [str(option).strip() for option in item["options"]]
            question.correct_index = int(item.get("correct_index", 0))
            question.explanation = (item.get("explanation") or "Answer verification pending.").strip()
            question.source_label = item.get(
                "source_label", "Official UPSC paper; independently verified explanation"
            ).strip()
            question.asset_url = item.get("asset_url") or None
            question.is_verified = bool(item.get("is_verified", False))

        await db.commit()
        return created, updated


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Path to a reviewed paper JSON file")
    args = parser.parse_args()
    payload = read_payload(args.file)
    created, updated = await import_payload(payload)
    print(f"Imported {args.file.name}: {created} created, {updated} updated")


if __name__ == "__main__":
    asyncio.run(main())
