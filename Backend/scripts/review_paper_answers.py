"""Create checked practice answers, without waiting for official keys.

Run from Backend after alembic upgrade head:
  python scripts/review_paper_answers.py --year 2026 --cycle I --subject english --apply

Dry-run by default (still uses the AI provider). Each batch is independently
solved twice without seeing proposed keys. Only agreement is saved, with honest
AI-checked provenance. Partial success survives a later provider outage. Reruns
skip existing checked answers. No student choices/timers are changed.
"""

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.models.papers import PaperAttempt, PreviousPaper
from app.models.practice import Subject
from app.services.paper_answer_review import review_batch
from app.services.paper_answers import refresh_attempt_grade, stored_answer
from app.services.paper_solver import PaperSolutionError
from app.services.rag import RagService, RagUnavailableError


async def run(args) -> None:
    # Scored content must not fall back to a lighter model. Two independent calls
    # are a check, not proof of official correctness.
    settings = get_settings().model_copy(
        update={
            "gemini_model": get_settings().practice_ai_model,
            "gemini_fallback_model": get_settings().practice_ai_model,
        }
    )
    tutor = RagService()
    tutor.settings = settings
    counts = Counter()
    try:
        async with SessionLocal() as db:
            paper = await db.scalar(
                select(PreviousPaper)
                .join(Subject)
                .options(
                    selectinload(PreviousPaper.subject),
                    selectinload(PreviousPaper.questions),
                )
                .where(
                    PreviousPaper.year == args.year,
                    PreviousPaper.cycle == args.cycle,
                    Subject.slug == args.subject,
                )
            )
            if not paper:
                raise ValueError("That paper is not in this database")
            questions = [q for q in paper.questions if not stored_answer(q, paper)][: args.limit]
            for start in range(0, len(questions), 10):
                batch = questions[start : start + 10]
                try:
                    result = await asyncio.wait_for(
                        review_batch(paper, batch, tutor._generate_paper_json, apply=args.apply),
                        timeout=120,
                    )
                except (RagUnavailableError, PaperSolutionError, TimeoutError) as exc:
                    await db.rollback()
                    print(
                        f"Review stopped safely: {exc}. Earlier completed batches remain saved.",
                        flush=True,
                    )
                    raise SystemExit(1) from None
                counts.update(result)
                if args.apply:
                    await db.commit()
                print(f"Q{batch[0].number}-Q{batch[-1].number}: {result}", flush=True)
            if args.apply:
                attempts = (
                    await db.scalars(
                        select(PaperAttempt)
                        .options(selectinload(PaperAttempt.answers))
                        .where(
                            PaperAttempt.paper_id == paper.id,
                            PaperAttempt.status == "completed",
                        )
                    )
                ).all()
                for attempt in attempts:
                    refresh_attempt_grade(
                        attempt, paper, list(paper.questions), list(attempt.answers)
                    )
                await db.commit()
    finally:
        print(f"Total: {dict(counts)}", flush=True)
        tutor.close()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--cycle", choices=["I", "II"], required=True)
    parser.add_argument(
        "--subject",
        choices=["english", "general-knowledge", "elementary-mathematics"],
        required=True,
    )
    parser.add_argument("--limit", type=int, choices=range(1, 341), default=120)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(run(parser.parse_args()))
