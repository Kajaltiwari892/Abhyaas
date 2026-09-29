"""Discover top-level CDS question numbers on newly released scan pages."""

from __future__ import annotations

import argparse
import asyncio
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
OUTPUT = PDF_ROOT / "page-ranges.json"

sys.path.insert(0, str(BACKEND))
from app.core.config import get_settings  # noqa: E402


def page_candidates() -> list[tuple[str, int]]:
    return (
        [("english", page) for page in range(2, 33)]
        + [("general-knowledge", page) for page in range(3, 57, 2)]
        + [("mathematics", page) for page in range(3, 41, 2)]
    )


def page_image(subject: str, page_number: int) -> str:
    filename = "mathematics.pdf" if subject == "mathematics" else f"{subject}.pdf"
    document = pymupdf.open(PDF_ROOT / filename)
    page = document[page_number - 1]
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.65, 1.65), colorspace=pymupdf.csGRAY)
    image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
    stream = io.BytesIO()
    image.save(stream, "WEBP", quality=86, method=6)
    return base64.b64encode(stream.getvalue()).decode("ascii")


async def main(args: argparse.Namespace) -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    saved = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    jobs = [job for job in page_candidates() if f"{job[0]}/page-{job[1]}" not in saved]
    lock = asyncio.Lock()
    limiter = asyncio.Lock()
    last_started = 0.0

    async def wait_rate() -> None:
        nonlocal last_started
        async with limiter:
            loop = asyncio.get_running_loop()
            delay = 60 / args.requests_per_minute - (loop.time() - last_started)
            if delay > 0:
                await asyncio.sleep(delay)
            last_started = loop.time()

    async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=20)) as client:
        async def process(subject: str, page: int) -> None:
            body = {
                "contents": [{"parts": [
                    {"inline_data": {"mime_type": "image/webp", "data": page_image(subject, page)}},
                    {"text": "Identify only the top-level numbered multiple-choice questions printed on this CDS exam page. Ignore numbered statements inside a question, option labels, page numbers, instructions, and handwritten/bleed-through text. Return JSON only as {\"numbers\":[1,2]}. If no top-level question begins on the page, return {\"numbers\":[]}."},
                ]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "maxOutputTokens": 512,
                    "thinkingConfig": {"thinkingLevel": "minimal"},
                },
            }
            last_error = "unknown"
            for attempt in range(2):
                await wait_rate()
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{args.model}:generateContent",
                    headers={"x-goog-api-key": settings.gemini_api_key},
                    json=body,
                )
                if response.status_code == 200:
                    try:
                        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                        payload = json.loads(text.strip().removeprefix("```json").removesuffix("```").strip())
                        numbers = sorted({int(number) for number in payload["numbers"] if 1 <= int(number) <= 120})
                        async with lock:
                            saved[f"{subject}/page-{page}"] = numbers
                            OUTPUT.write_text(json.dumps(dict(sorted(saved.items())), indent=2) + "\n", encoding="utf-8")
                            print(f"{subject}/page-{page}: {numbers}", flush=True)
                        return
                    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
                        last_error = str(exc)
                else:
                    last_error = f"HTTP {response.status_code}"
                if attempt == 0:
                    await asyncio.sleep(2)
            raise RuntimeError(f"{subject}/page-{page}: {last_error}")

        semaphore = asyncio.Semaphore(args.workers)

        async def limited(job: tuple[str, int]) -> None:
            async with semaphore:
                await process(*job)

        await asyncio.gather(*(limited(job) for job in jobs))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gemini-3.5-flash-lite")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--requests-per-minute", type=float, default=10)
    asyncio.run(main(parser.parse_args()))
