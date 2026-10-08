"""Dry-run by default. --apply adds checked-answer practice and retires only demo seeds.

All original paper records and previously attempted questions are preserved.
Run after `alembic upgrade head`; safe to run repeatedly.
"""

import argparse
import asyncio
import json
import sys
import uuid
from collections import Counter
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend"))

from app.db.session import SessionLocal, engine  # noqa: E402
from app.models.papers import PaperQuestion, PreviousPaper  # noqa: E402
from app.models.practice import Question, Subject, Topic  # noqa: E402
from app.services.practice_catalog import (  # noqa: E402
    IMPORT_BATCH,
    NAMESPACE,
    STARTER_IDS,
    prepare_question,
)


async def run(apply: bool) -> None:
    counts = Counter()
    topics_count = Counter()
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(PaperQuestion, PreviousPaper, Subject)
                .join(PreviousPaper, PreviousPaper.id == PaperQuestion.paper_id)
                .join(Subject, Subject.id == PreviousPaper.subject_id)
                .order_by(PaperQuestion.paper_id, PaperQuestion.number)
            )
        ).all()
        existing_topics = {
            (t.subject_id, t.slug): t for t in (await db.execute(select(Topic))).scalars()
        }
        existing = {q.id: q for q in (await db.execute(select(Question))).scalars()}
        accepted = {}
        english_directions = {}
        for question, paper, subject in rows:
            transcription = dict(question.transcription or {})
            if subject.slug == "english" and paper.year == 2025 and paper.cycle == "II":
                # Shared directions belong to bounded sections, not arbitrary
                # preceding questions. Never carry a passage between questions.
                boundaries = [1, 11, 21, 26, 31, 41, 51, 61, 71, 81, 91, 96, 101, 111]
                section = max(start for start in boundaries if start <= question.number)
                key = (paper.id, section)
                if transcription.get("directions") or transcription.get("sectionTitle"):
                    english_directions[key] = (
                        transcription.get("directions") or transcription["sectionTitle"]
                    )
                elif key in english_directions:
                    transcription["directions"] = english_directions[key]
            if (
                subject.slug == "elementary-mathematics"
                and paper.year == 2025
                and paper.cycle == "II"
            ):
                if question.number == 41:
                    english_directions[(paper.id, 41)] = transcription.get("directions")
                if question.number == 42 and not transcription.get("directions"):
                    transcription["directions"] = english_directions.get((paper.id, 41))
            record, reason = prepare_question(question, paper, subject.slug, transcription)
            if (
                record
                and not (
                    ROOT
                    / "Frontend"
                    / "abhyaas"
                    / "public"
                    / record["provenance"]["source_page_url"].lstrip("/")
                ).is_file()
            ):
                record, reason = None, "missing_source_image"
            if not record:
                counts[f"excluded_{reason}"] += 1
                continue
            if record["id"] in accepted:
                counts["duplicate_content"] += 1
                continue
            topic_slug, topic_name = record.pop("topic_slug"), record.pop("topic_name")
            key = (subject.id, topic_slug)
            topic = existing_topics.get(key)
            if topic is None:
                topic = Topic(
                    id=str(uuid.uuid5(NAMESPACE, f"topic:{subject.slug}:{topic_slug}")),
                    subject_id=subject.id,
                    slug=topic_slug,
                    name=topic_name,
                    position=len(existing_topics),
                )
                existing_topics[key] = topic
                if apply:
                    db.add(topic)
                    await db.flush()
            record["topic_id"] = topic.id
            accepted[record["id"]] = record
            topics_count[f"{subject.slug}/{topic_slug}"] += 1
            counts[f"accepted_{subject.slug}"] += 1
            if apply and record["id"] not in existing:
                db.add(Question(**record))
                counts["inserted"] += 1
            elif apply:
                existing[record["id"]].is_active = True
        # Safety: don't retire content if extraction produced no replacement pool.
        if apply and not accepted:
            raise RuntimeError("No eligible questions; existing catalog left unchanged")
        for question in existing.values():
            owned_import = (question.provenance or {}).get("import_batch") == IMPORT_BATCH
            if question.id in STARTER_IDS or (owned_import and question.id not in accepted):
                if apply:
                    question.is_active = False
                counts["retired_from_new_sets"] += int(question.is_active or apply)
        if apply:
            await db.commit()
    print(
        json.dumps(
            {
                "mode": "applied" if apply else "dry_run",
                "counts": dict(counts),
                "topics": dict(topics_count),
            },
            indent=2,
        )
    )
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(run(parser.parse_args().apply))
