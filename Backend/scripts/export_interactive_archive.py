"""Validate complete authoring checkpoints and export public question data/scans.

This does not grade questions, claim human text verification, or modify a database.
No partial paper is exported. Student data is never read.
"""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend"))

from scripts.transcribe_archive_papers import (  # noqa: E402
    CACHE,
    VERSION,
    archive_papers,
    checkpoint,
    expected_count,
    folder,
    validate_batch,
)


def collect(paper):
    directory = CACHE / folder(paper)
    source = directory / "source.pdf"
    if not source.exists():
        raise ValueError("Source PDF is missing")
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    with pymupdf.open(source) as doc:
        page_count = len(doc)
    questions = {}
    for path in sorted(directory.glob("questions-*-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("version") != VERSION
            or payload.get("source_checksum") != checksum
            or payload.get("source_url") != paper["source_url"]
        ):
            raise ValueError("Checkpoint does not match this source PDF/version")
        first, last = map(int, path.stem.split("-")[1:])
        for row in validate_batch(payload, first, last, page_count):
            if row["number"] in questions:
                raise ValueError("Overlapping transcription batches must be reconciled")
            questions[row["number"]] = {**row, "transcriptionSource": payload["model"]}
    if set(questions) != set(range(1, expected_count(paper) + 1)):
        raise ValueError(f"Only {len(questions)}/{expected_count(paper)} questions transcribed")
    rows = [questions[number] for number in sorted(questions)]
    if [r["page"] for r in rows] != sorted(r["page"] for r in rows):
        raise ValueError("Source pages are not in question order; review page mapping")
    # The whole-document draft is not publication-ready: every used page must
    # receive a separate image-based source comparison first.
    compared = {}
    for page in sorted({row["page"] for row in rows}):
        review_path = directory / "reviewed-pages" / f"page-{page}.json"
        if not review_path.exists():
            raise ValueError(f"Source comparison pending for page {page}")
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if review["source_checksum"] != checksum:
            raise ValueError("Source comparison checksum mismatch")
        page_numbers = [r["number"] for r in rows if r["page"] == page]
        reviewed = validate_batch(review, min(page_numbers), max(page_numbers), page_count)
        for row in reviewed:
            if row["page"] != page:
                raise ValueError("Source comparison page mapping differs")
            compared[row["number"]] = {
                **row,
                "transcriptionSource": review["model"],
                "source_compared": True,
            }
    rows = [compared[number] for number in sorted(questions)]
    for row in rows:
        row["text_reviewed"] = False
        row["sourcePageUrl"] = f"{paper['source_url']}#page={row['page']}"
        row["transcriptionVersion"] = VERSION
    return {
        "year": paper["year"],
        "cycle": paper["cycle"],
        "subject_slug": paper["subject_slug"],
        "source_url": paper["source_url"],
        "source_checksum": checksum,
        "question_count": expected_count(paper),
        "questions": rows,
    }, source


def render_pages(paper, source):
    destination = ROOT / "Frontend/abhyaas/public/papers" / folder(paper)
    destination.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(source) as document:
        for number in sorted({question["page"] for question in paper["questions"]}):
            path = destination / f"page-{number}.webp"
            if not path.exists():
                pixmap = document[number - 1].get_pixmap(
                    matrix=pymupdf.Matrix(1.8, 1.8), colorspace=pymupdf.csGRAY
                )
                image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
                image.save(path, "WEBP", quality=86, method=6)
    for row in paper["questions"]:
        row["asset_url"] = f"/papers/{folder(paper)}/page-{row['page']}.webp"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-incomplete-archive",
        action="store_true",
        help="Export complete papers only; report all pending papers explicitly",
    )
    args = parser.parse_args()
    papers, pending = [], []
    sources = []
    for entry in archive_papers():
        if args.folder and folder(entry) != args.folder:
            continue
        try:
            paper, source = collect(entry)
            papers.append(paper)
            sources.append(source)
        except ValueError as exc:
            pending.append(f"{folder(entry)}: {exc}")
    if pending and not args.allow_incomplete_archive:
        raise ValueError("Archive is incomplete:\n" + "\n".join(pending))
    if not papers:
        raise ValueError("No complete papers to export")
    for paper, source in zip(papers, sources, strict=True):
        render_pages(paper, source)
    bundle = {
        "version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "description": "Source-linked AI transcriptions; text review and answer keys "
        "are separate. No answers generated, no student data.",
        "papers": papers,
    }
    checkpoint(args.output, bundle)
    print(
        f"Exported {len(papers)} complete papers, "
        f"{sum(p['question_count'] for p in papers)} questions"
    )
    for message in pending:
        print("PENDING " + message)


if __name__ == "__main__":
    main()
