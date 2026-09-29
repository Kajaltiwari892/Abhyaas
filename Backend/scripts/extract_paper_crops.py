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
from PIL import Image
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


def render_question_images(crops: dict[str, dict[str, float | int | str]]) -> None:
    """Write stable per-question images instead of cropping via CSS at runtime.

    A little extra space is retained above and around each OCR crop. This keeps
    printed question numbers and ascenders intact without including the next
    question in the same image.
    """
    opened: dict[Path, Image.Image] = {}
    try:
        for key, crop in crops.items():
            asset_url, number_text = key.rsplit("#", 1)
            source = PUBLIC_PAPERS / asset_url.removeprefix("/papers/")
            image = opened.setdefault(source, Image.open(source).convert("RGB"))
            width, height = image.size

            crop_left = float(crop["x"])
            crop_top = float(crop["y"])
            crop_right = crop_left + float(crop["width"])
            crop_bottom = crop_top + float(crop["height"])
            # Keep the complete printed number at the outside/centre gutter,
            # while stopping precisely at the opposite column boundary.
            left = 0 if crop_left < 0.1 else max(0, round((crop_left - 0.038) * width))
            top = max(0, round((crop_top - 0.012) * height))
            right = min(width, round(crop_right * width))
            bottom = min(height, round(crop_bottom * height))

            output_directory = source.parent / "questions"
            output_directory.mkdir(parents=True, exist_ok=True)
            output = output_directory / f"question-{int(number_text):03d}.webp"
            question_image = image.crop((left, top, right, bottom))
            question_image.save(output, "WEBP", quality=88, method=6)
            crop["imageUrl"] = (
                f"{asset_url.rsplit('/', 1)[0]}/questions/question-"
                f"{int(number_text):03d}.webp"
            )
            crop["pixelWidth"], crop["pixelHeight"] = question_image.size
    finally:
        for image in opened.values():
            image.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder", help="Extract one archive folder, for example cds-i-2026/english"
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="Rebuild question image files from the existing crop manifest",
    )
    args = parser.parse_args()
    if args.render_only:
        existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
        selected = {
            key: value
            for key, value in existing.items()
            if not args.folder or key.startswith(f"/papers/{args.folder}/")
        }
        render_question_images(selected)
        existing.update(selected)
        OUTPUT.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        print(f"Rendered {len(selected)} question images")
        return
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
    render_question_images(crops)
    OUTPUT.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {len(crops)} verified crop locations to {OUTPUT}")
    if failures:
        print("\nOCR validation failures:")
        print("\n".join(failures))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
