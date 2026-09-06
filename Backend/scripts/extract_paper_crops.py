"""Locate each printed question in the official paper scans with OCR.

This is a content-authoring utility, not a runtime dependency. Install
``rapidocr-onnxruntime`` in the backend virtual environment before running it.
It writes normalized crop coordinates consumed by the papers UI, allowing the
student to see one exact official question instead of an entire scanned page.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from types import ModuleType

import cv2
from rapidocr_onnxruntime import RapidOCR

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_PAPERS = ROOT / "Frontend" / "abhyaas" / "public" / "papers"
OUTPUT = ROOT / "Frontend" / "abhyaas" / "lib" / "paper-crops.json"
_ENGINE: RapidOCR | None = None


def load_migration(filename: str) -> ModuleType:
    path = ROOT / "Backend" / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifests() -> list[tuple[str, list[tuple[int, int, int]]]]:
    old = load_migration("20260902_07_complete_cds_2024.py")
    recent = load_migration("20260903_08_add_cds_2025_2026.py")
    result: list[tuple[str, list[tuple[int, int, int]]]] = []
    for subject, ranges in old.PAGE_RANGES.items():
        result.append((f"cds-i-2024/{subject}", ranges))
    for (year, cycle, subject), ranges in recent.PAGE_RANGES.items():
        folder = recent.PAPERS[(year, cycle)]["folder"]
        result.append((f"{folder}/{subject}", ranges))
    return result


def question_markers(results: list, width: int, height: int, first: int, last: int):
    expected = set(range(first, last + 1))
    markers: dict[int, tuple[float, float, float]] = {}
    for box, text, confidence in results:
        confidence = float(confidence)
        match = re.match(r"^\s*(\d{1,3})[.)]\s*", text.strip())
        if not match or int(match.group(1)) not in expected or confidence < 0.55:
            continue
        number = int(match.group(1))
        x = min(point[0] for point in box)
        top = min(point[1] for point in box)
        in_left_gutter = x < width * 0.25
        in_right_gutter = width * 0.42 < x < width * 0.75
        if height * 0.035 < top < height * 0.94 and (in_left_gutter or in_right_gutter):
            previous = markers.get(number)
            if previous is None or confidence > previous[2]:
                markers[number] = (x, top, confidence)
    return markers


def extract_page(job: tuple[str, int, int, int]):
    global _ENGINE
    folder, page, first, last = job
    relative = f"/papers/{folder}/page-{page}.webp"
    path = PUBLIC_PAPERS / folder / f"page-{page}.webp"
    image = cv2.imread(str(path))
    if image is None:
        return {}, f"missing image: {path}"
    height, width = image.shape[:2]
    if _ENGINE is None:
        _ENGINE = RapidOCR()
    results, _ = _ENGINE(str(path))
    markers = question_markers(results or [], width, height, first, last)
    missing = sorted(set(range(first, last + 1)) - set(markers))
    if missing:
        return {}, f"{folder}/page-{page}: missing {missing}"

    page_crops: dict[str, dict[str, float | int]] = {}
    by_column: dict[str, list[tuple[int, float]]] = {"left": [], "right": []}
    for number, (x, top, _) in markers.items():
        by_column["left" if x < width * 0.4 else "right"].append((number, top))
    for column, items in by_column.items():
        items.sort(key=lambda item: item[1])
        for index, (number, top) in enumerate(items):
            next_top = items[index + 1][1] if index + 1 < len(items) else height * 0.925
            left = 0.045 if column == "left" else 0.515
            right = 0.515 if column == "left" else 0.975
            y = max(0.025, (top - 18) / height)
            bottom = min(0.94, (next_top - 12) / height)
            page_crops[f"{relative}#{number}"] = {
                "x": round(left, 5),
                "y": round(y, 5),
                "width": round(right - left, 5),
                "height": round(max(0.04, bottom - y), 5),
                "pixelWidth": round((right - left) * width),
                "pixelHeight": round(max(0.04, bottom - y) * height),
            }
    return page_crops, None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder", help="Extract one archive folder, for example cds-i-2026/english"
    )
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    crops: dict[str, dict[str, float | int]] = {}
    failures: list[str] = []
    jobs = [
        (folder, page, first, last)
        for folder, ranges in manifests()
        if not args.folder or folder == args.folder
        for page, first, last in ranges
    ]
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(extract_page, job): job for job in jobs}
        for index, future in enumerate(as_completed(futures), start=1):
            page_crops, failure = future.result()
            crops.update(page_crops)
            if failure:
                failures.append(failure)
            if index % 10 == 0 or index == len(jobs):
                print(f"Processed {index}/{len(jobs)} scan pages")

    existing = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    existing.update(crops)
    OUTPUT.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {len(crops)} verified crop locations to {OUTPUT}")
    if failures:
        print("\nOCR validation failures:")
        print("\n".join(failures))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
