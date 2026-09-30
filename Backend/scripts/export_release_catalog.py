"""Generate the release's public study content; never export account or activity data.

Run after the reviewed paper/key imports and import_practice_catalog.py. The explicit
column allowlists below deliberately exclude every user, attempt and chat table.
"""

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, engine  # noqa: E402
from app.models.papers import PaperQuestion, PreviousPaper  # noqa: E402
from app.models.practice import Question, Topic  # noqa: E402
from app.services.practice_catalog import IMPORT_BATCH, STARTER_IDS  # noqa: E402


async def export() -> None:
    async with SessionLocal() as db:
        question_fields = (
            "id",
            "topic_id",
            "prompt",
            "context",
            "options",
            "correct_index",
            "explanation",
            "source_label",
            "difficulty",
            "is_active",
            "provenance",
        )
        candidates = (await db.execute(select(Question).order_by(Question.id))).scalars()
        questions = [
            {key: getattr(q, key) for key in question_fields}
            for q in candidates
            if q.is_active and (q.provenance or {}).get("import_batch") == IMPORT_BATCH
        ]
        topic_ids = {q["topic_id"] for q in questions}
        topics = [
            {key: getattr(t, key) for key in ("id", "subject_id", "slug", "name", "position")}
            for t in (await db.execute(select(Topic).order_by(Topic.id))).scalars()
            if t.id in topic_ids
        ]
        paper_questions = [
            {key: getattr(q, key) for key in ("id", "paper_id", "number", "transcription")}
            for q in (await db.execute(select(PaperQuestion).order_by(PaperQuestion.id))).scalars()
            if q.transcription
        ]
        papers = list(
            (
                await db.execute(
                    select(PreviousPaper)
                    .where(PreviousPaper.year == 2025, PreviousPaper.cycle == "II")
                    .order_by(PreviousPaper.id)
                )
            ).scalars()
        )
        keys = [
            {
                key: getattr(q, key)
                for key in (
                    "id",
                    "paper_id",
                    "number",
                    "correct_index",
                    "is_verified",
                    "source_label",
                    "explanation",
                )
            }
            for q in (
                await db.execute(
                    select(PaperQuestion)
                    .where(PaperQuestion.paper_id.in_([p.id for p in papers]))
                    .order_by(PaperQuestion.id)
                )
            ).scalars()
            if q.is_verified and q.source_label.startswith("Official UPSC")
        ]
        assert len(questions) == 292 and len(paper_questions) == 1700 and len(keys) == 340
        bundle = {
            "version": 1,
            "description": (
                "Public UPSC paper transcriptions, final 2025 II keys and scored practice. "
                "No student data."
            ),
            "topics": topics,
            "questions": questions,
            "paper_questions": paper_questions,
            "answer_keys": keys,
            "papers": [
                {
                    key: getattr(p, key)
                    for key in (
                        "id",
                        "year",
                        "cycle",
                        "source_url",
                        "answer_key_url",
                    )
                }
                for p in papers
            ],
            "retire_question_ids": STARTER_IDS,
        }
    destination = ROOT / "data" / "release_catalog_20261001.json"
    destination.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Public catalog exported: {len(questions)} practice, "
        f"{len(paper_questions)} transcriptions, {len(keys)} official keys"
    )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(export())
