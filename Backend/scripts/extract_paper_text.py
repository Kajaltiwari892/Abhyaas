"""OCR verified per-question scan crops into student-facing structured text.

Only questions with a prompt and four independently detected answer choices are
published. Complex diagrams/tables deliberately fall back to the source crop.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image
from rapidocr_onnxruntime import RapidOCR

ROOT = Path(__file__).resolve().parents[2]
CROPS = ROOT / "Frontend" / "abhyaas" / "lib" / "paper-crops.json"
OUTPUT = ROOT / "Frontend" / "abhyaas" / "lib" / "paper-question-text.json"


def bounds(row: list) -> tuple[float, float, float, float]:
    box = row[0]
    return (
        min(point[0] for point in box),
        min(point[1] for point in box),
        max(point[0] for point in box),
        max(point[1] for point in box),
    )


def repair_text(text: str) -> str:
    text = re.sub(r"\s+([,.;:?!])", r"\1", text)
    text = re.sub(r"(?i)([a-z])and([A-Z])", r"\1 and \2", text)
    repairs = {
        "meansabamboo": "means a bamboo",
        "meansagroup": "means a group",
        "temporarybridge": "temporary bridge",
        "wasconsidered": "was considered",
        "inmeaningto": "in meaning to",
        "beneficiaryvia": "beneficiary via",
        "Agreementfor": "Agreement for",
        "emeans": "means",
        "theassertion": "the assertion",
        "Climaticmeansscientific": "Climatic means scientific",
        "Imminentmeans": "Imminent means",
        "Incrediblmeans": "Incredible means",
        "amongthefollowing": "among the following",
        "andledtheTokugawatoput": "and led the Tokugawa to put",
        "asphaltroads": "asphalt roads",
        "bybiological": "by biological",
        "difficulttobelieve": "difficult to believe",
        "eightyNormannobleswhohad": "eighty Norman nobles who had",
        "extremelylarge": "extremely large",
        "involvementof": "involvement of",
        "littleknowledge": "little knowledge",
        "recoveryofpatients": "recovery of patients",
        "studiesfamilies": "studies families",
        "theenvironment": "the environment",
        "thewillingness": "the willingness",
        "tohelpnavigatediscourses": "to help navigate discourses",
        "toofficially": "to officially",
        "verydifficult": "very difficult",
        "willingness understand": "willingness to understand",
        "immanent'": "immanent",
        "sciencehad": "science had",
        "becomea": "become a",
        "withnature": "with nature",
        "thefirst": "the first",
        "exp and ed": "expanded",
        "alot": "a lot",
        "The“": "The “",
    }
    for source, replacement in repairs.items():
        text = text.replace(source, replacement)
    text = re.sub(r"\s+KPRS-F-NGE(?:\s.*)?$", "", text)
    text = re.sub(r"\s+\d{1,3}\.$", "", text)
    text = re.sub(r"^Sl:", "S1:", text)
    text = text.replace("“asphalt complex\"", "“asphalt complex”")
    return re.sub(r"\s+", " ", text).strip()


def join_rows(rows: list[list]) -> str:
    if not rows:
        return ""
    ordered = sorted(rows, key=lambda row: (bounds(row)[1], bounds(row)[0]))
    lines: list[list[list]] = []
    for row in ordered:
        top = bounds(row)[1]
        if not lines or abs(top - sum(bounds(item)[1] for item in lines[-1]) / len(lines[-1])) > 9:
            lines.append([row])
        else:
            lines[-1].append(row)
    text = " ".join(
        " ".join(str(item[1]).strip() for item in sorted(line, key=lambda row: bounds(row)[0]))
        for line in lines
    )
    return repair_text(text)


def parse_question(number: int, rows: list[list]) -> dict[str, object] | None:
    rows = [row for row in rows if float(row[2]) >= 0.48]
    question_pattern = re.compile(rf"^\s*{number}[.)]\s*")
    question_row = next((row for row in rows if question_pattern.match(str(row[1]))), None)
    if question_row is None:
        return None
    question_left, question_top, _, _ = bounds(question_row)
    max_right = max((bounds(row)[2] for row in rows), default=1)
    useful = [
        row
        for row in rows
        if bounds(row)[2] >= max(0, question_left - 7)
        and bounds(row)[0] <= max_right * 0.96
        and bounds(row)[1] >= question_top - 5
        and not re.match(r"^\(\d+\s*[-–]\s*[A-Z]\)$", str(row[1]).strip())
    ]

    marker_pattern = re.compile(r"^\(([a-dq])\)$", re.IGNORECASE)
    candidates = [row for row in useful if marker_pattern.match(str(row[1]).strip())]
    candidates.sort(key=lambda row: bounds(row)[1])
    markers: list[list] = []
    expected = ["a", "b", "c", "d"]
    for row in candidates:
        label = marker_pattern.match(str(row[1]).strip()).group(1).lower()  # type: ignore[union-attr]
        if label == "q" and len(markers) == 1:
            label = "b"
        if len(markers) < 4 and label == expected[len(markers)]:
            markers.append(row)
    if len(markers) != 4:
        return None

    marker_centres = [(bounds(marker)[1] + bounds(marker)[3]) / 2 for marker in markers]
    first_option_top = marker_centres[0] - 10
    prompt_rows = [
        row for row in useful if (bounds(row)[1] + bounds(row)[3]) / 2 < first_option_top
    ]
    prompt = question_pattern.sub("", join_rows(prompt_rows), count=1).strip()
    options: list[str] = []
    for index, marker in enumerate(markers):
        start = marker_centres[index] - 10
        end = marker_centres[index + 1] - 10 if index < 3 else float("inf")
        option_rows = [
            row
            for row in useful
            if start <= (bounds(row)[1] + bounds(row)[3]) / 2 < end and row is not marker
        ]
        options.append(join_rows(option_rows))

    if len(prompt) < 5 or any(len(option) < 2 for option in options):
        return None
    confidence_values = [float(row[2]) for row in useful]
    return {
        "prompt": prompt,
        "options": options,
        "ocrConfidence": round(sum(confidence_values) / len(confidence_values), 3),
    }


def inspect_directions() -> None:
    engine = RapidOCR()
    page_directory = ROOT / "Frontend" / "abhyaas" / "public" / "papers" / "cds-i-2026" / "english"
    pages = sorted(
        page_directory.glob("page-*.webp"),
        key=lambda path: int(path.stem.split("-")[1]),
    )
    for page in pages:
        rows, _ = engine(str(page))
        rows = rows or []
        direction_rows = [row for row in rows if "direction" in str(row[1]).lower()]
        if not direction_rows:
            continue
        print(f"\n=== {page.name} ===", flush=True)
        for direction in direction_rows:
            left, top, right, _ = bounds(direction)
            column_right = max(right + 520, 650)
            nearby = [
                row
                for row in rows
                if top - 8 <= bounds(row)[1] <= top + 310
                and bounds(row)[0] >= left - 30
                and bounds(row)[0] <= column_right
            ]
            print(join_rows(nearby), flush=True)


def main() -> None:
    if "--inspect-directions" in sys.argv:
        inspect_directions()
        return
    if "--repair-existing" in sys.argv:
        extracted = json.loads(OUTPUT.read_text(encoding="utf-8"))
        for question in extracted.values():
            question["prompt"] = repair_text(str(question["prompt"]))
            question["options"] = [repair_text(str(option)) for option in question["options"]]
        OUTPUT.write_text(
            json.dumps(extracted, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Repaired {len(extracted)} structured questions in {OUTPUT}")
        return
    engine = RapidOCR()
    crops = json.loads(CROPS.read_text(encoding="utf-8"))
    extracted: dict[str, dict[str, object]] = {}
    pages: dict[str, list[tuple[str, dict[str, object]]]] = {}
    for key, crop in crops.items():
        if "/cds-i-2026/english/" not in key:
            continue
        asset_url, _ = key.rsplit("#", 1)
        pages.setdefault(asset_url, []).append((key, crop))

    for page_index, (asset_url, entries) in enumerate(sorted(pages.items()), start=1):
        source = ROOT / "Frontend" / "abhyaas" / "public" / asset_url.removeprefix("/")
        page_rows, _ = engine(str(source))
        with Image.open(source) as page_image:
            width, height = page_image.size
        for key, crop in entries:
            number = int(key.rsplit("#", 1)[1])
            crop_left = float(crop["x"])
            crop_top = float(crop["y"])
            crop_right = crop_left + float(crop["width"])
            crop_bottom = crop_top + float(crop["height"])
            left = 0 if crop_left < 0.1 else max(0, round((crop_left - 0.038) * width))
            top = max(0, round((crop_top - 0.012) * height))
            right = min(width, round(crop_right * width))
            bottom = min(height, round(crop_bottom * height))
            local_rows = []
            for row in page_rows or []:
                row_left, row_top, row_right, row_bottom = bounds(row)
                centre_x = (row_left + row_right) / 2
                centre_y = (row_top + row_bottom) / 2
                if left <= centre_x <= right and top <= centre_y <= bottom:
                    shifted_box = [[point[0] - left, point[1] - top] for point in row[0]]
                    local_rows.append([shifted_box, row[1], row[2]])
            parsed = parse_question(number, local_rows)
            if parsed:
                extracted[key] = parsed
        print(f"Processed page {page_index}/{len(pages)} ({len(extracted)} structured)", flush=True)
    OUTPUT.write_text(json.dumps(extracted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(extracted)} structured questions to {OUTPUT}")


if __name__ == "__main__":
    main()
