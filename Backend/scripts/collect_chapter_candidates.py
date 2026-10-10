"""Find source pages for chapter review; never publish snippets as PYQs or call an AI.

Run from Backend. Downloads are bounded and cached by the official archive authoring
utility. Scanned pages are explicitly reported as pending unless --ocr is selected.
Only a separate reviewed bundle can be imported into the shared question bank.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend"))

from scripts.transcribe_archive_papers import MANIFEST, checkpoint, download, folder  # noqa: E402

SOUND_CANDIDATE = re.compile(
    r"\bsound\b|\bacoustic\w*|\bultraso\w*|\binfraso\w*|\bdoppler\b|"
    r"\becho(?:es)?\b|\bsonar\b|\bdecibel\w*|\baudib\w*|\bhearing\b|"
    r"\bwavelength\b|\bfrequency\b|\boscillat\w*|\bvibrat\w*",
    re.I,
)


def collect(
    paper: dict, *, ocr=None, max_ocr_pages: int = 0, selected_pages=None, render_only=False
) -> dict:
    path, _, checksum, pages, _ = download(paper)
    candidates, pending, ocr_used = [], [], 0
    destination = ROOT / "tmp/pdfs/chapter-review" / folder(paper)
    with pymupdf.open(path) as document:
        for index, page in enumerate(document):
            if selected_pages and index + 1 not in selected_pages:
                pending.append(index + 1)
                continue
            if index % 10 == 0:
                print(
                    f"CDS {paper['cycle']} {paper['year']}: scanning page {index + 1}/{pages}",
                    flush=True,
                )
            text = page.get_text()
            method = "visual-review-pending" if render_only else "pdf-text"
            # A few cover/header characters are not usable question text.
            if not render_only and len(re.findall(r"[A-Za-z]{3,}", text)) < 25:
                if ocr is None or ocr_used >= max_ocr_pages:
                    pending.append(index + 1)
                    continue
                import numpy as np

                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.7, 1.7), alpha=False)
                pixels = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                    pixmap.height, pixmap.width, pixmap.n
                )
                cached = destination / f"ocr-page-{index + 1}.json"
                payload = json.loads(cached.read_text(encoding="utf-8")) if cached.exists() else {}
                if payload.get("source_checksum") == checksum:
                    text = payload["text"]
                else:
                    results, _ = ocr(pixels)
                    text = "\n".join(row[1] for row in results or [])
                    checkpoint(cached, {"source_checksum": checksum, "text": text})
                method = "ocr-draft"
                ocr_used += 1
                if len(re.findall(r"[A-Za-z]{3,}", text)) < 25:
                    pending.append(index + 1)
                    continue
            if not render_only and not SOUND_CANDIDATE.search(text):
                continue
            destination.mkdir(parents=True, exist_ok=True)
            image = destination / f"page-{index + 1}.png"
            page.get_pixmap(matrix=pymupdf.Matrix(1.7, 1.7), alpha=False).save(image)
            candidates.append(
                {
                    "page": index + 1,
                    "method": method,
                    "text": text,
                    "review_image": str(image),
                    "reviewed": False,
                }
            )
    return {
        "year": paper["year"],
        "cycle": paper["cycle"],
        "subject_slug": paper["subject_slug"],
        "source_url": paper["source_url"],
        "source_checksum": checksum,
        "page_count": pages,
        "pending_pages": pending,
        "candidates": candidates,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, nargs="+", required=True)
    parser.add_argument("--cycle", choices=["I", "II"])
    parser.add_argument("--max-papers", type=int, default=4)
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--max-ocr-pages", type=int, default=60)
    parser.add_argument(
        "--pages", type=int, nargs="+", help="Physical PDF pages to inspect; others remain pending"
    )
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="Render selected pages for visual review without OCR",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.max_papers <= 21 or not 0 <= args.max_ocr_pages <= 100:
        parser.error("Authoring limits exceeded")
    if args.pages and any(not 1 <= page <= 100 for page in args.pages):
        parser.error("Pages must be physical PDF page numbers between 1 and 100")
    if args.ocr and args.render_only:
        parser.error("Choose OCR extraction or visual-only rendering, not both")
    ocr = None
    if args.ocr:
        from rapidocr_onnxruntime import RapidOCR

        # Some older RapidOCR releases expose no thread setting and let each
        # model take every CPU core. Bound those sessions for authoring laptops.
        from rapidocr_onnxruntime import utils as ocr_utils

        session_options = ocr_utils.SessionOptions

        def bounded_options():
            options = session_options()
            options.intra_op_num_threads = 2
            options.inter_op_num_threads = 1
            return options

        ocr_utils.SessionOptions = bounded_options
        try:
            ocr = RapidOCR(use_angle_cls=False)
        finally:
            ocr_utils.SessionOptions = session_options
    papers = [
        p
        for p in json.loads(MANIFEST.read_text(encoding="utf-8"))["papers"]
        if p["subject_slug"] == "general-knowledge"
        and p["year"] in args.years
        and (not args.cycle or p["cycle"] == args.cycle)
    ]
    selected = sorted(papers, key=lambda p: (p["year"], p["cycle"]), reverse=True)[
        : args.max_papers
    ]
    report = {
        "version": 1,
        "chapter": "sound-waves",
        "papers": [],
        "not_scanned": len(papers) - len(selected),
    }
    for paper in selected:
        result = collect(
            paper,
            ocr=ocr,
            max_ocr_pages=args.max_ocr_pages,
            selected_pages=args.pages,
            render_only=args.render_only,
        )
        report["papers"].append(result)
        checkpoint(args.output, report)
        print(
            f"CDS {paper['cycle']} {paper['year']}: {len(result['candidates'])} candidate pages; "
            f"{len(result['pending_pages'])} pages pending",
            flush=True,
        )
    print("Draft pages only. Compare each question/options with the original before importing.")


if __name__ == "__main__":
    main()
