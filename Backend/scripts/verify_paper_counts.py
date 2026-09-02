"""Print imported and verified question totals for every previous paper."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import Integer, func, select

from app.db.session import SessionLocal
from app.models.papers import PaperQuestion, PreviousPaper
from app.models.practice import Subject


async def main() -> None:
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(
                    PreviousPaper.year,
                    PreviousPaper.cycle,
                    Subject.slug,
                    PreviousPaper.official_question_count,
                    func.count(PaperQuestion.id),
                    func.sum(func.cast(PaperQuestion.is_verified, Integer)),
                )
                .join(PreviousPaper, PreviousPaper.subject_id == Subject.id)
                .join(PaperQuestion, PaperQuestion.paper_id == PreviousPaper.id)
                .group_by(
                    PreviousPaper.year,
                    PreviousPaper.cycle,
                    Subject.slug,
                    PreviousPaper.official_question_count,
                )
                .order_by(PreviousPaper.year, PreviousPaper.cycle, Subject.slug)
            )
        ).all()
    for year, cycle, slug, official, imported, verified in rows:
        status = "OK" if official == imported else "MISMATCH"
        print(
            f"CDS {cycle} {year} {slug}: official={official}, imported={imported}, "
            f"verified={verified} [{status}]"
        )


if __name__ == "__main__":
    asyncio.run(main())
