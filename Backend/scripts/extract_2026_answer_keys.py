"""Extract and cross-check Series A keys from the official CDS II 2026 PDFs."""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path

import httpx
import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "Backend"
PDF_ROOT = ROOT / "tmp" / "pdfs" / "cds-ii-2026"
OUTPUT = PDF_ROOT / "answer-keys.json"
SUBJECTS = {
    "english": ("answer-english.pdf", 120),
    "general-knowledge": ("answer-general-knowledge.pdf", 120),
    "elementary-mathematics": ("answer-mathematics.pdf", 100),
}

sys.path.insert(0, str(BACKEND))
from app.core.config import get_settings  # noqa: E402


def first_page_image(filename: str) -> str:
    with pymupdf.open(PDF_ROOT / filename) as document:
        pixmap = document[0].get_pixmap(
            matrix=pymupdf.Matrix(1.7, 1.7), colorspace=pymupdf.csGRAY
        )
    image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
    stream = io.BytesIO()
    image.save(stream, "WEBP", quality=90, method=6)
    return base64.b64encode(stream.getvalue()).decode("ascii")


def extract_text(payload: dict[str, object]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("response has no candidates")
    parts = candidates[0]["content"]["parts"]  # type: ignore[index]
    return "".join(part.get("text", "") for part in parts if isinstance(part, dict))


def parse_key(raw: str, count: int) -> str:
    payload = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
    answers = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(answers, list):
        raise ValueError("response does not contain an answers array")
    parsed: dict[int, str] = {}
    for entry in answers:
        if not isinstance(entry, dict):
            continue
        number = int(entry.get("number", 0))
        answer = str(entry.get("answer", "")).strip().upper()
        if 1 <= number <= count and answer in "ABCDX" and len(answer) == 1:
            parsed[number] = answer
    missing = sorted(set(range(1, count + 1)) - set(parsed))
    if missing:
        raise ValueError(f"missing answers: {missing}")
    return "".join(parsed[number] for number in range(1, count + 1))


def main(args: argparse.Namespace) -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    saved = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    with httpx.Client(timeout=httpx.Timeout(90, connect=20)) as client:
        for model in args.models:
            model_results = saved.setdefault(model, {})
            for subject, (filename, count) in SUBJECTS.items():
                if subject in model_results:
                    continue
                body = {
                    "contents": [{"parts": [
                        {"inline_data": {
                            "mime_type": "image/webp",
                            "data": first_page_image(filename),
                        }},
                        {"text": (
                            "This is page 1 of an official UPSC provisional answer-key PDF. "
                            "Read ONLY the table headed TEST BOOKLET SERIES - A. Ignore Series B, "
                            "C and D if visible. Preserve X for any dropped question. "
                            "Return every entry in JSON only as "
                            "{\"answers\":[{\"number\":1,\"answer\":\"A\"}]}. "
                            f"The Series A table must contain questions 1 through {count} exactly "
                            "once. Preserve the printed answer letters; do not solve the questions."
                        )},
                    ]}],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "maxOutputTokens": 4096,
                    },
                }
                last_error: Exception | None = None
                for _attempt in range(3):
                    response = client.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                        headers={"x-goog-api-key": settings.gemini_api_key},
                        json=body,
                    )
                    response.raise_for_status()
                    try:
                        key = parse_key(extract_text(response.json()), count)
                        break
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                        last_error = exc
                else:
                    raise RuntimeError(f"Could not extract {subject} with {model}: {last_error}")
                model_results[subject] = key
                OUTPUT.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
                print(f"{model} {subject}: {key}", flush=True)

    baseline_model = args.models[0]
    for subject in SUBJECTS:
        baseline = saved[baseline_model][subject]
        for model in args.models[1:]:
            candidate = saved[model][subject]
            disagreements = [
                number
                for number, (left, right) in enumerate(zip(baseline, candidate), start=1)
                if left != right
            ]
            print(f"compare {subject} {baseline_model} vs {model}: {disagreements}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models", nargs="+", default=["gemini-3.5-flash-lite", "gemini-2.5-flash"]
    )
    main(parser.parse_args())
