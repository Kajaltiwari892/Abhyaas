"""Read-only smoke check. --live spends one solver batch on the configured AI provider.

No users, conversations, paper records or answer keys are written. Default: inspect only.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.db.session import SessionLocal, engine  # noqa: E402
from app.models.papers import PreviousPaper  # noqa: E402
from app.models.practice import Subject  # noqa: E402
from app.services.paper_solver import _source_problem  # noqa: E402
from app.services.rag import RagService, RagUnavailableError  # noqa: E402


async def main(live: bool) -> None:
    service = RagService()
    try:
        async with SessionLocal() as db:
            paper = await db.scalar(
                select(PreviousPaper)
                .join(Subject)
                .options(selectinload(PreviousPaper.questions))
                .where(
                    PreviousPaper.year == 2026,
                    PreviousPaper.cycle == "I",
                    Subject.slug == "english",
                    PreviousPaper.is_published.is_(True),
                )
            )
            if not paper:
                raise SystemExit("2026 CDS I English is not in this database.")
            print(
                json.dumps(
                    {
                        "paper": paper.title,
                        "stored_questions": len(paper.questions),
                        "readable_questions": sum(
                            _source_problem(q) is None for q in paper.questions
                        ),
                        "blocked": [
                            {"number": q.number, "reason": _source_problem(q)}
                            for q in paper.questions
                            if _source_problem(q)
                        ],
                        "first_question": paper.questions[0].transcription
                        if paper.questions
                        else None,
                    },
                    ensure_ascii=True,
                )
            )
            if live:
                result = await service.answer(
                    db, "Solve CDS I 2026 English questions 1 to 10", None, []
                )
                data = result.pyq_result
                print(
                    json.dumps(
                        {
                            "kind": result.answer_kind,
                            "status": data["status"],
                            "returned": len(data["questions"]),
                            "solutions": [
                                {"number": q["number"], **q["solution"]} for q in data["questions"]
                            ],
                        },
                        ensure_ascii=True,
                    )
                )
    except RagUnavailableError as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        service.close()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    asyncio.run(main(parser.parse_args().live))
