r"""Transcribe every official CDS paper page into structured question text.

The paper viewer must not depend on fragile image crops.  This authoring tool
sends each complete official scan page to the configured Gemini vision model,
validates that every expected question and all four choices were returned, and
checkpoints the result in ``paper-question-text.json`` after every page.

Run from ``Backend`` after setting ``GEMINI_API_KEY`` in ``.env``::

    .\.venv\Scripts\python.exe .\scripts\transcribe_paper_questions.py

The command is resumable.  Existing complete entries are retained unless
``--replace`` is supplied.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import importlib.util
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "Backend"
PUBLIC_PAPERS = ROOT / "Frontend" / "abhyaas" / "public" / "papers"
OUTPUT = ROOT / "Frontend" / "abhyaas" / "lib" / "paper-question-text.json"
MANUAL_OUTPUT = ROOT / "Frontend" / "abhyaas" / "lib" / "paper-question-manual.json"
DEFAULT_MODEL = "gemini-2.5-flash"
TRANSCRIPTION_VERSION = 2

sys.path.insert(0, str(BACKEND))
from app.core.config import get_settings  # noqa: E402


@dataclass(frozen=True)
class PageJob:
    folder: str
    subject: str
    page: int
    first: int
    last: int
    previous_page: int | None

    @property
    def asset_url(self) -> str:
        return f"/papers/{self.folder}/{self.subject}/page-{self.page}.webp"

    @property
    def label(self) -> str:
        return f"{self.folder}/{self.subject}/page-{self.page} (Q{self.first}-Q{self.last})"


class RequestRateLimiter:
    def __init__(self, requests_per_minute: float) -> None:
        self.interval = 60 / max(1, requests_per_minute)
        self.lock = asyncio.Lock()
        self.last_started = 0.0

    async def wait(self) -> None:
        async with self.lock:
            loop = asyncio.get_running_loop()
            delay = self.interval - (loop.time() - self.last_started)
            if delay > 0:
                await asyncio.sleep(delay)
            self.last_started = loop.time()


def load_migration(filename: str) -> ModuleType:
    path = BACKEND / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def page_jobs() -> list[PageJob]:
    old = load_migration("20260902_07_complete_cds_2024.py")
    recent = load_migration("20260903_08_add_cds_2025_2026.py")
    latest = load_migration("20260917_11_add_cds_ii_2026.py")
    manifests: list[tuple[str, str, list[tuple[int, int, int]]]] = []
    for subject, ranges in old.PAGE_RANGES.items():
        manifests.append(("cds-i-2024", subject, ranges))
    for (year, cycle, subject), ranges in recent.PAGE_RANGES.items():
        manifests.append((recent.PAPERS[(year, cycle)]["folder"], subject, ranges))
    for subject, ranges in latest.PAGE_RANGES.items():
        manifests.append(("cds-ii-2026", subject, ranges))

    jobs: list[PageJob] = []
    for folder, subject, ranges in manifests:
        for index, (page, first, last) in enumerate(ranges):
            previous_page = ranges[index - 1][0] if subject == "english" and index else None
            jobs.append(PageJob(folder, subject, page, first, last, previous_page))
    return jobs


def is_complete(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    prompt = entry.get("prompt")
    options = entry.get("options")
    return (
        isinstance(prompt, str)
        and len(prompt.strip()) >= 2
        and isinstance(options, list)
        and len(options) == 4
        and all(isinstance(option, str) and option.strip() for option in options)
    )


def expected_keys(job: PageJob) -> list[str]:
    return [f"{job.asset_url}#{number}" for number in range(job.first, job.last + 1)]


def clean_string(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text


def validate_transcription(
    job: PageJob, text: str, model: str
) -> dict[str, dict[str, object]]:
    payload = json.loads(strip_json_fence(text))
    questions = payload.get("questions") if isinstance(payload, dict) else payload
    if not isinstance(questions, list):
        raise ValueError("response does not contain a questions array")

    parsed: dict[int, dict[str, object]] = {}
    for raw in questions:
        if not isinstance(raw, dict):
            continue
        try:
            number = int(raw.get("number"))
        except (TypeError, ValueError):
            continue
        if number < job.first or number > job.last:
            continue
        prompt = clean_string(raw.get("prompt"))
        raw_options = raw.get("options")
        if not isinstance(raw_options, list) or len(raw_options) != 4:
            continue
        options = [clean_string(option) for option in raw_options]
        if len(prompt) < 2 or any(not option for option in options):
            continue
        entry: dict[str, object] = {
            "prompt": re.sub(rf"^\s*{number}\s*[.)]\s*", "", prompt, count=1),
            "options": [
                re.sub(
                    r"^\s*(?:\([a-dA-D]\)|[a-dA-D][.)])\s+(?=\S)",
                    "",
                    option,
                    count=1,
                )
                for option in options
            ],
            "transcriptionSource": model,
            "transcriptionVersion": TRANSCRIPTION_VERSION,
        }
        for source, target in (
            ("sectionTitle", "sectionTitle"),
            ("directions", "directions"),
            ("passage", "passage"),
            ("visualDescription", "visualDescription"),
        ):
            value = clean_string(raw.get(source))
            if value:
                entry[target] = value
        entry["hasVisual"] = bool(raw.get("hasVisual", False))
        parsed[number] = entry

    missing = sorted(set(range(job.first, job.last + 1)) - set(parsed))
    if missing:
        raise ValueError(f"missing or invalid questions: {missing}")
    return {f"{job.asset_url}#{number}": parsed[number] for number in sorted(parsed)}


def prompt_for(job: PageJob, has_previous_page: bool) -> str:
    context_note = (
        "The first image is the preceding English page and the second image is the target page. "
        "Use the preceding page only to recover a heading, directions, or passage that clearly "
        "continues into the target questions. "
        if has_previous_page
        else "The supplied image is the target page. "
    )
    return f"""You are doing exact document transcription, not answering an exam.

{context_note}Transcribe every target question numbered {job.first} through {job.last} from the official CDS paper page. Return JSON only in this exact shape:
{{"questions":[{{"number":{job.first},"sectionTitle":null,"directions":null,"passage":null,"prompt":"complete printed question","options":["complete option A","complete option B","complete option C","complete option D"],"hasVisual":false,"visualDescription":null}}]}}

Rules:
- Return every number from {job.first} through {job.last} exactly once and in order.
- Copy the printed wording completely. Do not solve, summarize, paraphrase, modernize, or invent text.
- Do not put the leading question number in prompt or the A/B/C/D marker in option strings.
- Keep numbered statements, List I/List II material, match codes, equations, units, qualifications, and blanks inside the prompt or relevant option.
- Use plain Unicode text and line breaks for formulas, fractions, tables, and lists so a student can read them without the scan.
- If a diagram, graph, map, or figure is essential, set hasVisual true and describe only its printed labels and geometry faithfully in visualDescription. Never infer an answer.
- sectionTitle, directions, and passage must contain only text printed in the image(s) and clearly applicable to the target question. Otherwise use null.
- Ignore page numbers, booklet codes, headers, footers, and any Hindi text from facing bilingual pages.
- Four non-empty options are required for every question.
"""


def image_part(path: Path) -> dict[str, object]:
    return {
        "inline_data": {
            "mime_type": "image/webp",
            "data": base64.b64encode(path.read_bytes()).decode("ascii"),
        }
    }


def request_parts(job: PageJob) -> list[dict[str, object]]:
    directory = PUBLIC_PAPERS / job.folder / job.subject
    parts: list[dict[str, object]] = []
    # A single complete target page is both faster and less ambiguous than a
    # pair of neighbouring pages.  Directions/passages printed on a section's
    # opening page are still captured there and can be shared by the UI.
    has_previous_page = False
    parts.extend(
        [
            image_part(directory / f"page-{job.page}.webp"),
            {"text": prompt_for(job, has_previous_page)},
        ]
    )
    return parts


async def transcribe_page(
    client: httpx.AsyncClient,
    api_key: str,
    model: str,
    job: PageJob,
    semaphore: asyncio.Semaphore,
    rate_limiter: RequestRateLimiter,
) -> dict[str, dict[str, object]]:
    generation_config: dict[str, object] = {
        "responseMimeType": "application/json",
        "maxOutputTokens": 16384,
    }
    if model.startswith("gemini-3"):
        # Gemini 3 is optimized for its default temperature.  For exact
        # transcription, minimal thinking controls latency without the empty
        # responses caused by legacy temperature=0 settings.
        generation_config["thinkingConfig"] = {"thinkingLevel": "minimal"}
    else:
        generation_config["temperature"] = 0
        generation_config["thinkingConfig"] = {"thinkingBudget": 0}
    body = {
        "contents": [{"parts": request_parts(job)}],
        "generationConfig": generation_config,
    }
    last_error = "unknown error"
    for attempt in range(1, 3):
        async with semaphore:
            try:
                await rate_limiter.wait()
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": api_key},
                    json=body,
                )
            except httpx.HTTPError as exc:
                last_error = str(exc)
            else:
                if response.status_code == 200:
                    try:
                        result_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                        return validate_transcription(job, result_text, model)
                    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
                        last_error = str(exc)
                elif response.status_code in {429, 500, 502, 503, 504}:
                    last_error = f"HTTP {response.status_code}"
                else:
                    detail = response.text[:300].replace("\n", " ")
                    raise RuntimeError(f"{job.label}: HTTP {response.status_code}: {detail}")
        if attempt < 2:
            await asyncio.sleep(min(30, 2**attempt))
    raise RuntimeError(f"{job.label}: failed after retries ({last_error})")


def write_checkpoint(data: dict[str, dict[str, object]]) -> None:
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(dict(sorted(data.items())), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for attempt in range(10):
        try:
            os.replace(temporary, OUTPUT)
            return
        except PermissionError:
            if attempt == 9:
                raise
            # OneDrive can briefly hold the destination while indexing it.
            time.sleep(0.25 * (attempt + 1))


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in Backend/.env")
    data: dict[str, dict[str, object]] = (
        json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    )
    manual: dict[str, dict[str, object]] = (
        json.loads(MANUAL_OUTPUT.read_text(encoding="utf-8"))
        if MANUAL_OUTPUT.exists()
        else {}
    )
    combined = {**data, **manual}

    def current_or_manual(key: str) -> bool:
        if is_complete(manual.get(key)):
            return True
        entry = data.get(key)
        return is_complete(entry) and (
            not args.replace or entry.get("transcriptionVersion") == TRANSCRIPTION_VERSION
        )

    selected = [
        job
        for job in page_jobs()
        if (not args.folder or f"{job.folder}/{job.subject}" == args.folder)
        and f"{job.folder}/{job.subject}" not in args.exclude_folder
        and not all(current_or_manual(key) for key in expected_keys(job))
    ]
    if args.max_pages:
        selected = selected[: args.max_pages]
    if not selected:
        print(f"All {len(combined)} structured questions are already complete.", flush=True)
        return

    print(
        f"Transcribing {len(selected)} pages with {args.workers} workers; "
        f"{len(data)} questions already present.",
        flush=True,
    )
    semaphore = asyncio.Semaphore(max(1, args.workers))
    rate_limiter = RequestRateLimiter(args.requests_per_minute)
    lock = asyncio.Lock()
    completed = 0
    failures: list[str] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=20)) as client:
        async def process(job: PageJob) -> None:
            nonlocal completed
            try:
                page_data = await transcribe_page(
                    client,
                    settings.gemini_api_key,
                    args.model,
                    job,
                    semaphore,
                    rate_limiter,
                )
            except Exception as exc:  # Continue so successful pages remain checkpointed.
                async with lock:
                    failures.append(str(exc))
                    completed += 1
                    print(f"[{completed}/{len(selected)}] FAILED {job.label}: {exc}", flush=True)
                return
            async with lock:
                if args.replace:
                    data.update(page_data)
                else:
                    for key, value in page_data.items():
                        if not is_complete(data.get(key)) and not is_complete(manual.get(key)):
                            data[key] = value
                write_checkpoint(data)
                completed += 1
                print(
                    f"[{completed}/{len(selected)}] {job.label} -> {len(data)} total",
                    flush=True,
                )

        await asyncio.gather(*(process(job) for job in selected))

    scope_jobs = [
        job
        for job in page_jobs()
        if not args.folder or f"{job.folder}/{job.subject}" == args.folder
    ]
    scope_keys = {key for job in scope_jobs for key in expected_keys(job)}
    expected_total = len(scope_keys)
    combined = {**data, **manual}
    complete_total = sum(is_complete(combined.get(key)) for key in scope_keys)
    print(f"Complete structured questions in scope: {complete_total}/{expected_total}", flush=True)
    if failures:
        print("Pages to retry:", flush=True)
        for failure in failures:
            print(f"- {failure}", flush=True)
        raise SystemExit(1)
    if complete_total != expected_total and not args.max_pages:
        raise RuntimeError(f"Expected {expected_total} complete questions, found {complete_total}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder",
        help="Limit to one folder/subject, for example cds-i-2026/general-knowledge",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--requests-per-minute",
        type=float,
        default=10,
        help="Pace API calls to stay below the model quota",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Process at most this many currently incomplete pages",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Retranscribe complete existing entries as well as missing entries",
    )
    parser.add_argument(
        "--exclude-folder",
        action="append",
        default=[],
        help="Skip a folder/subject; may be supplied more than once",
    )
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
