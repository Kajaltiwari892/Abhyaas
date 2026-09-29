"""Render the authoritative UPSC scans used by the previous-paper viewer.

Download the three PDFs into ``tmp/pdfs/cds-i-2024`` using the filenames below,
then run this script from the repository root. Generated WebP files are written
to the frontend public directory. Keeping the scan in the UI prevents OCR from
changing mathematical notation, diagrams, or wording.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PDF_ROOT = ROOT / "tmp" / "pdfs"
PUBLIC_ROOT = ROOT / "Frontend" / "abhyaas" / "public" / "papers"

PAPER_PAGES = {
    "cds-i-2024": {
        "english": ("english.pdf", range(2, 29)),
        "general-knowledge": ("general-knowledge.pdf", range(3, 46, 2)),
        "elementary-mathematics": ("mathematics.pdf", range(3, 36, 2)),
    },
    "cds-i-2025": {
        "english": ("english.pdf", range(2, 29)),
        "general-knowledge": ("general-knowledge.pdf", range(3, 36, 2)),
        "elementary-mathematics": ("mathematics.pdf", range(3, 28, 2)),
    },
    "cds-ii-2025": {
        "english": ("english.pdf", range(2, 25)),
        "general-knowledge": ("general-knowledge.pdf", range(3, 44, 2)),
        "elementary-mathematics": ("mathematics.pdf", range(3, 44, 2)),
    },
    "cds-i-2026": {
        "english": ("english.pdf", range(2, 21)),
        "general-knowledge": ("general-knowledge.pdf", range(3, 44, 2)),
        "elementary-mathematics": ("mathematics.pdf", range(3, 44, 2)),
    },
}


def render_paper(folder: str, slug: str, pdf_name: str, pages: range) -> None:
    source = PDF_ROOT / folder / pdf_name
    if not source.exists():
        raise FileNotFoundError(f"Download the official paper first: {source}")
    output = PUBLIC_ROOT / folder / slug
    output.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open(source)
    for page_number in pages:
        page = document[page_number - 1]
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2.2, 2.2), colorspace=pymupdf.csGRAY)
        temporary = output / f"page-{page_number}.png"
        destination = output / f"page-{page_number}.webp"
        pixmap.save(temporary)
        with Image.open(temporary) as image:
            image.save(destination, "WEBP", quality=82, method=6)
        temporary.unlink()
        print(destination.relative_to(ROOT))


def main() -> None:
    for folder, papers in PAPER_PAGES.items():
        for slug, (pdf_name, pages) in papers.items():
            render_paper(folder, slug, pdf_name, pages)


if __name__ == "__main__":
    main()
