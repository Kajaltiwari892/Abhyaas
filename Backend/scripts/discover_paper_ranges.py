"""Print likely CDS question-number ranges for each scanned PDF page.

This is an authoring aid for adding a newly released paper. It renders pages in
memory, runs RapidOCR, and reports question-number markers found in the two
printed column gutters. The output is reviewed against page images before it is
copied into an Alembic paper manifest.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from rapidocr_onnxruntime import RapidOCR


def markers(rows: list, width: int, height: int) -> list[int]:
    found: set[int] = set()
    for box, text, confidence in rows:
        if float(confidence) < 0.48:
            continue
        match = re.match(r"^\s*(\d{1,3})\s*[.)]", str(text))
        if not match:
            continue
        number = int(match.group(1))
        if not 1 <= number <= 120:
            continue
        left = min(point[0] for point in box)
        top = min(point[1] for point in box)
        if height * 0.035 < top < height * 0.94 and (
            left < width * 0.2 or width * 0.46 < left < width * 0.7
        ):
            found.add(number)
    return sorted(found)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--odd-only", action="store_true")
    args = parser.parse_args()
    engine = RapidOCR()
    document = pymupdf.open(args.pdf)
    for index, page in enumerate(document):
        page_number = index + 1
        if args.odd_only and page_number % 2 == 0:
            continue
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.05, 1.05), colorspace=pymupdf.csGRAY)
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width)
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        rows, _ = engine(image)
        numbers = markers(rows or [], pixmap.width, pixmap.height)
        if numbers:
            print(f"page {page_number}: {numbers}", flush=True)


if __name__ == "__main__":
    main()
