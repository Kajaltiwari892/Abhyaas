"""Import checked, non-official answers. Dry-run unless --apply is supplied.

  python scripts/import_reviewed_paper_answers.py
    data/reviewed_answers/cds-i-2026-english.json --apply

The full source checksum and each question fingerprint must match. Reviewed
answers are saved separately; original official keys and user choices are kept.
Run scripts/import_practice_catalog.py --apply afterwards to make eligible,
complete questions available in subject practice too.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal, engine
from app.services.reviewed_answer_import import import_reviews


async def run(path: Path, apply: bool) -> None:
    try:
        async with SessionLocal() as db:
            payload = json.loads(path.read_text(encoding="utf-8"))
            counts = await import_reviews(db, payload, apply=apply)
            print(json.dumps({"mode": "applied" if apply else "dry_run", **counts}))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.file, args.apply))
