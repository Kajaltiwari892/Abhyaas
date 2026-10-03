"""Second-pass scan comparison for draft transcriptions; no DB writes or answer keys.

Works on full-resolution neighbouring page images rather than a large whole-PDF
context. It preserves drafts and writes separate checkpoints for source comparison.
This automated pass is not labelled human verification.
"""

import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend"))

from app.core.config import get_settings  # noqa: E402
from scripts.transcribe_archive_papers import (  # noqa: E402
    CACHE,
    Limits,
    archive_papers,
    checkpoint,
    download,
    folder,
    image_document,
    transcribe,
)


async def run(args):
    settings = get_settings()
    args.model = args.model or settings.gemini_model
    limits = Limits(args.rpm, args.max_calls)
    failures = []
    papers = [p for p in archive_papers() if folder(p) == args.folder]
    if len(papers) != 1:
        raise ValueError("Choose one archive folder")
    paper = papers[0]
    path, _, checksum, pages, _ = download(paper)
    directory = CACHE / folder(paper)
    drafts = []
    for batch in sorted(directory.glob("questions-*-*.json")):
        payload = json.loads(batch.read_text(encoding="utf-8"))
        if payload["source_checksum"] != checksum:
            raise ValueError("Mismatched source checksum")
        drafts.extend(payload["questions"])
    by_page = {}
    for row in drafts:
        by_page.setdefault(row["page"], []).append(row)
    await asyncio.to_thread(image_document, path)
    selected = [page for page in sorted(by_page) if not args.page or page in args.page]
    semaphore = asyncio.Semaphore(3)
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=25)) as client:

        async def review(page):
            target = directory / "reviewed-pages" / f"page-{page}.json"
            if target.exists():
                saved = json.loads(target.read_text(encoding="utf-8"))
                if saved.get("source_checksum") == checksum:
                    print(f"CACHED page {page}", flush=True)
                    return
            rows = sorted(by_page[page], key=lambda row: row["number"])
            parts = [
                {
                    "text": f"Target physical PDF page: {page}. Neighbour pages are context only. "
                    "Copy both columns of every matching table; preserve exactly which word is "
                    "underlined. For ordering questions, write P: phrase, Q: phrase, R: phrase, "
                    "S: phrase so labels cannot become detached. For error spotting, each "
                    "choice must contain its entire underlined segment, not just (a)/(b)/(c). "
                    "Do not accidentally include option letters twice. The following earlier "
                    "draft may have OCR omissions/errors: compare and correct it against the "
                    "images, never assume it is correct. Retain a shared passage only if it "
                    "applies to this question.\n" + json.dumps(rows, ensure_ascii=False)
                }
            ]
            for number in range(max(1, page - 1), min(pages, page + 1) + 1):
                image_path = directory / "input-pages" / f"page-{number}.webp"
                parts.extend(
                    [
                        {"text": f"Physical PDF page {number}:"},
                        {
                            "inline_data": {
                                "mime_type": "image/webp",
                                "data": base64.b64encode(image_path.read_bytes()).decode("ascii"),
                            }
                        },
                    ]
                )
            async with semaphore:
                try:
                    result, usage = await transcribe(
                        client,
                        paper,
                        parts,
                        rows[0]["number"],
                        rows[-1]["number"],
                        pages,
                        args,
                        limits,
                        settings.gemini_api_key,
                    )
                    if any(row["page"] != page for row in result):
                        raise ValueError("Page mapping differs from draft; inspect manually")
                    checkpoint(
                        target,
                        {
                            "source_checksum": checksum,
                            "questions": result,
                            "model": args.model,
                            "usage": usage,
                        },
                    )
                    print(
                        f"REVIEWED page {page}: Q{rows[0]['number']}-{rows[-1]['number']}",
                        flush=True,
                    )
                except (RuntimeError, ValueError) as exc:
                    failures.append(f"Page {page}: {exc}")
                    print("FAILED " + failures[-1], flush=True)

        await asyncio.gather(*(review(page) for page in selected))
    print(f"Review calls: {limits.calls}; failed pages: {len(failures)}", flush=True)
    if failures:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", required=True)
    parser.add_argument("--page", type=int, action="append")
    parser.add_argument("--model")
    parser.add_argument("--max-calls", type=int, default=45)
    parser.add_argument("--rpm", type=float, default=12)
    args = parser.parse_args()
    if not 1 <= args.max_calls <= 100 or not 1 <= args.rpm <= 30:
        parser.error("Use bounded request limits")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
