"""Import existing source-linked transcriptions into the shared backend question bank.

Run without --apply for a dry run. Never changes answer keys or the legacy source records.
Re-importing identical text is idempotent; a changed checksum invalidates its text review.
"""

import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend"))

from app.db.session import SessionLocal, engine  # noqa: E402
from app.models.papers import PaperQuestion, PreviousPaper  # noqa: E402
from app.services.question_bank import classify_topics, text_checksum  # noqa: E402


def prepare_record(key: str, record: dict, subject: str, reviewed: dict) -> dict:
    if not isinstance(record.get("prompt"), str) or not record["prompt"].strip():
        raise ValueError(f"Empty prompt: {key}")
    options = record.get("options")
    if (
        not isinstance(options, list)
        or len(options) != 4
        or not all(isinstance(option, str) and option.strip() for option in options)
    ):
        raise ValueError(f"Invalid options: {key}")
    page_url = record.get("sourcePageUrl") or key.split("#")[0]
    if not re.fullmatch(r"/papers/cds-(?:i|ii)-20\d{2}/[a-z-]+/page-\d+\.webp", page_url):
        raise ValueError(f"Invalid local source page: {key}")
    checksum = text_checksum(record)
    review = reviewed.get(key, {})
    verified = review.get("checksum") == checksum
    return {
        **record,
        "sourcePageUrl": page_url,
        "source_page": int(re.search(r"page-(\d+)", page_url)[1]),
        "checksum": checksum,
        "topics": review["topics"] if verified else classify_topics(record, subject),
        "text_reviewed": verified,
        "review_note": review.get("note") if verified else None,
    }


async def run(apply: bool) -> None:
    library = ROOT / "Frontend" / "abhyaas" / "lib"
    records = json.loads((library / "paper-question-text.json").read_text(encoding="utf-8"))
    records.update(json.loads((library / "paper-question-manual.json").read_text(encoding="utf-8")))
    reviews = json.loads(
        (ROOT / "Backend" / "data" / "question_text_reviews.json").read_text(encoding="utf-8")
    )
    counts = Counter()
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(PaperQuestion, PreviousPaper)
                .join(PreviousPaper)
                .options(selectinload(PreviousPaper.subject))
            )
        ).all()
        matched_keys = set()
        for question, paper in rows:
            key = f"{question.asset_url}#{question.number}"
            record = records.get(key)
            if not record:
                counts["missing_text"] += 1
                continue
            expected_prefix = (
                f"/papers/cds-{paper.cycle.lower()}-{paper.year}/{paper.subject.slug}/"
            )
            if not key.startswith(expected_prefix):
                raise ValueError(f"Paper/source mismatch: {key}")
            prepared = prepare_record(key, record, paper.subject.slug, reviews)
            if not (
                ROOT / "Frontend" / "abhyaas" / "public" / prepared["sourcePageUrl"].lstrip("/")
            ).is_file():
                raise ValueError(f"Missing source page: {key}")
            matched_keys.add(key)
            counts["indexed"] += 1
            counts["text_reviewed"] += int(prepared["text_reviewed"])
            counts["tagged"] += bool(prepared["topics"])
            if prepared != question.transcription:
                counts["changed"] += 1
                if apply:
                    question.transcription = prepared
        counts["unmatched_source_entries"] = len(records.keys() - matched_keys)
        if apply:
            await db.commit()
    print(json.dumps({"mode": "applied" if apply else "dry_run", **counts}, indent=2))
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(run(parser.parse_args().apply))
