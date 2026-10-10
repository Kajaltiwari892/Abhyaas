"""Validate a reviewed chapter bundle. Dry-run by default; --apply stores public PYQs.

Never imports student/account data, answer keys, or generated practice as PYQs.
Use a new versioned release migration to publish the same content in production.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import engine  # noqa: E402
from app.services.chapter_publication import publish  # noqa: E402


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    bundle = json.loads(args.file.read_text(encoding="utf-8"))
    # New questions must have their exact source-page image ready for the viewer.
    for paper in bundle["papers"]:
        for question in paper["questions"]:
            asset = (
                ROOT.parent
                / "Frontend/abhyaas/public/papers"
                / (
                    f"cds-{paper['cycle'].lower()}-{paper['year']}/{paper['subject_slug']}/page-{question['page']}.webp"
                )
            )
            if not asset.is_file():
                raise ValueError(f"Source page asset missing: {asset}")
    async with engine.begin() as connection:
        counts = await connection.run_sync(lambda conn: publish(conn, bundle, apply=args.apply))
    print(json.dumps({"mode": "applied" if args.apply else "dry-run", **counts}, indent=2))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
