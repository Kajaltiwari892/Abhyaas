"""Package a source-compared chapter draft and exact PDF page images for release.

This is an authoring step, not a database import. It verifies paper URL/checksum,
computes question checksums and refuses to overwrite a versioned release bundle.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend"))

from app.services.chapter_publication import validate_bundle  # noqa: E402
from app.services.question_bank import text_checksum  # noqa: E402
from scripts.transcribe_archive_papers import MANIFEST, checkpoint, download, folder  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new filename; never replace a published release bundle")
    bundle = json.loads(args.draft.read_text(encoding="utf-8"))
    archive = {
        (p["year"], p["cycle"], p["subject_slug"]): p
        for p in json.loads(MANIFEST.read_text(encoding="utf-8"))["papers"]
    }
    sources = []
    for paper in bundle["papers"]:
        official = archive.get((paper["year"], paper["cycle"], paper["subject_slug"]))
        if not official or official["source_url"] != paper["source_url"]:
            raise ValueError("Source is not in the official UPSC archive manifest")
        source = (
            ROOT
            / "tmp/pdfs"
            / f"cds-{paper['cycle'].lower()}-{paper['year']}"
            / (f"{paper['subject_slug']}.pdf")
        )
        if not source.is_file():
            source, _, _, _, _ = download(official)
        if hashlib.sha256(source.read_bytes()).hexdigest() != paper["source_checksum"]:
            raise ValueError("Reviewed PDF checksum differs from the cached original")
        for question in paper["questions"]:
            checksum = text_checksum(question)
            if question.get("checksum") and question["checksum"] != checksum:
                raise ValueError("Reviewed question text changed")
            question["checksum"] = checksum
        sources.append(source)
    validate_bundle(bundle)
    # Validate all source pages before producing any deliverable assets.
    for paper, source in zip(bundle["papers"], sources, strict=True):
        with pymupdf.open(source) as document:
            if any(q["page"] > len(document) for q in paper["questions"]):
                raise ValueError("Question source page is outside the original PDF")
    for paper, source in zip(bundle["papers"], sources, strict=True):
        destination = ROOT / "Frontend/abhyaas/public/papers" / folder(paper)
        destination.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(source) as document:
            for page in sorted({q["page"] for q in paper["questions"]}):
                asset = destination / f"page-{page}.webp"
                if asset.exists():
                    continue
                pixmap = document[page - 1].get_pixmap(
                    matrix=pymupdf.Matrix(1.8, 1.8), colorspace=pymupdf.csGRAY
                )
                Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples).save(
                    asset, "WEBP", quality=86, method=6
                )
    checkpoint(args.output, bundle)
    print(
        f"Packaged {sum(len(p['questions']) for p in bundle['papers'])} source-compared PYQs. "
        "Answer keys and student data were not changed."
    )


if __name__ == "__main__":
    main()
