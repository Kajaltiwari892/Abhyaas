"""Build scored practice from complete, source-linked, checked paper records.

This is a content gate, not a claim that OCR has been manually reviewed. Provisional
keys without a stored answer, missing contexts and image-dependent questions are excluded.
"""

import hashlib
import json
import re
import uuid
from urllib.parse import urlparse

from app.models.papers import PaperQuestion, PreviousPaper
from app.services.paper_answers import stored_answer

IMPORT_BATCH = "cds-official-v1"
NAMESPACE = uuid.UUID("1ad65892-4ff8-4c91-a986-9f641f739c1b")
SEED_NAMESPACE = uuid.UUID("7207de75-09b3-4b08-bf78-abe86f898c91")
STARTER_IDS = [str(uuid.uuid5(SEED_NAMESPACE, f"question:{i}")) for i in range(15)]


def official_url(value: str | None) -> bool:
    url = urlparse(value or "")
    return url.scheme == "https" and url.hostname in {"upsc.gov.in", "www.upsc.gov.in"}


def practice_topic(subject: str, record: dict) -> tuple[str, str]:
    text = " ".join(
        " ".join(
            str(record.get(k, "")) for k in ("sectionTitle", "directions", "prompt", "passage")
        )
        .lower()
        .split()
    )
    tags = set(record.get("topics") or [])
    if subject == "english":
        if "no error" in " ".join(record.get("options", [])).lower() or "spotting error" in text:
            return "error-spotting", "Error spotting"
        if any(
            word in text
            for word in (
                "six sentences",
                "proper sequence",
                "jumbled",
                "co-relationship",
                "ordering",
                "parts of a sentence",
            )
        ):
            return "sentence-ordering", "Sentence ordering and relationships"
        if "passage" in text and record.get("passage"):
            return "comprehension", "Comprehension"
        if any(word in text for word in ("idiom", "phrase means")):
            return "idioms", "Idioms and phrases"
        if any(
            word in text
            for word in (
                "meaning",
                "synonym",
                "antonym",
                "word / expression",
                "underlined word",
                "particular word",
            )
        ):
            return "vocabulary", "Vocabulary"
        if any(
            word in text
            for word in (
                "preposition",
                "determiner",
                "part of speech",
                "parts of speech",
                "word class",
                "blank space",
            )
        ):
            return "grammar", "Grammar"
        return "mixed-english", "Mixed English"
    if subject == "general-knowledge":
        groups = [
            ("history", "History", {"ancient-history", "medieval-history", "modern-history"}),
            (
                "geography",
                "Geography",
                {"earth-interior", "rocks-minerals", "weather-climate", "rivers-oceans"},
            ),
            ("polity", "Polity", {"constitution", "parliament"}),
            ("economics", "Economics", {"economy"}),
            ("general-science", "General Science", {"physics", "chemistry", "biology"}),
        ]
        matching = [(slug, name) for slug, name, members in groups if tags & members]
        if len(matching) == 1:
            return matching[0]
        return "mixed-gk", "Mixed GK / other topics"
    if re.search(r"(?:sin|cos|tan|cot|sec|cosec)\b|(?:sin|cos|tan|cot|sec|cosec)[θ²^]", text):
        return "trigonometry", "Trigonometry"
    if re.search(r"volume|surface area|cylinder|cone|sphere|cuboid|hemisphere", text):
        return "mensuration", "Mensuration"
    if re.search(r"polynomial|equation|factor of|x\^|x\}\^|x\^\{|a\^|b\^", text):
        return "algebra", "Algebra"
    for tag, name in [
        ("mensuration", "Mensuration"),
        ("trigonometry", "Trigonometry"),
        ("geometry", "Geometry"),
        ("algebra", "Algebra"),
    ]:
        if tag in tags:
            return tag, name
    return "arithmetic", "Arithmetic and data interpretation"


def prepare_question(
    question: PaperQuestion,
    paper: PreviousPaper,
    subject: str,
    record_override: dict | None = None,
) -> tuple[dict | None, str]:
    record = record_override if record_override is not None else question.transcription or {}
    if (
        question.is_verified
        and isinstance(record.get("options"), list)
        and len(record["options"]) != 4
    ):
        return None, "incomplete_options"
    key = stored_answer(question, paper)
    if not paper.is_published or key is None or not official_url(paper.source_url):
        return None, "no_final_official_key"
    # Legacy verified demo answers without an official key are not bulk-imported.
    if question.is_verified and (
        not official_url(paper.answer_key_url)
        or (key.basis != "provisional" and not question.source_label.startswith("Official UPSC"))
    ):
        return None, "no_final_official_key"
    prompt = record.get("prompt", "")
    options = record.get("options", [])
    if not isinstance(prompt, str) or not prompt.strip() or not isinstance(options, list):
        return None, "incomplete_text"
    if len(options) != 4 or not all(isinstance(o, str) and o.strip() for o in options):
        return None, "incomplete_options"
    if len({o.strip().casefold() for o in options}) != 4 or not 0 <= key.index < 4:
        return None, "invalid_options_or_key"
    if record.get("hasVisual"):
        return None, "visual_question"
    page = record.get("sourcePageUrl", "")
    if not re.fullmatch(r"/papers/cds-(?:i|ii)-20\d{2}/[a-z-]+/page-\d+\.webp", page):
        return None, "missing_source_page"
    directions = "\n".join(
        dict.fromkeys(
            str(record[k]).strip() for k in ("sectionTitle", "directions") if record.get(k)
        )
    )
    passage = str(record.get("passage") or "").strip()
    context = "\n\n".join(part for part in (directions, passage) if part)
    instructions = directions.lower()
    # Audited omissions in this transcription: missing error segments, emphasis,
    # and full cloze passages. Do not silently manufacture missing source text.
    known_paper = paper.year == 2025 and paper.cycle == "II"
    if (
        known_paper
        and subject == "english"
        and (
            11 <= question.number <= 20
            or 26 <= question.number <= 30
            or 51 <= question.number <= 60
            or 81 <= question.number <= 90
            or question.number >= 111
        )
    ):
        return None, "incomplete_english_section"
    if (
        not passage
        and len(directions) < 120
        and re.fullmatch(
            r"(?:select|choose) (?:the (?:correct )?(?:answer|option))"
            r"(?: using the code given below)?\s*[:.?]*",
            prompt.strip(),
            re.I,
        )
    ):
        return None, "missing_context"
    if "match list" in prompt.lower() and len(prompt) < 140 and not passage:
        return None, "missing_lists"
    if "underlined" in instructions and not re.search(r"<u>.+?</u>", prompt, re.S):
        return None, "missing_underlined_target"
    if (
        ("passage" in instructions or "given above" in prompt.lower())
        and not passage
        and not re.search(r"\b1[.) :]|\bI[.) :]|\bS1\s*:", prompt)
    ):
        return None, "missing_context"
    if re.search(r"\b(?:figure|diagram|graph)\s+(?:given|shown|below)", prompt, re.I):
        return None, "visual_question"
    # Fragmented cloze extraction is not safe to score. A standalone blank is fine.
    if re.search(r"\b\d{2,3}\.\s*[_]+", prompt) or ("cloze" in instructions and not passage):
        return None, "fragmented_cloze"
    if re.search(r"(?:[�]|\[illegible\]|\[missing\])", prompt + context, re.I):
        return None, "unreadable_text"
    if re.search(
        r"(?:missing from|not (?:visible|provided) in|unable to (?:read|extract))", prompt, re.I
    ):
        return None, "missing_text"
    topic_slug, topic_name = practice_topic(subject, record)
    if known_paper and subject == "general-knowledge":
        n = question.number
        # Topic audit of this paper's prompts, not a text-verification claim.
        if 21 <= n <= 50 or 81 <= n <= 85:
            topic_slug, topic_name = "general-science", "General Science"
        elif 51 <= n <= 70 or n in {1, 10, 11, 13, 14, 15, 20}:
            topic_slug, topic_name = "history", "History"
        elif 86 <= n <= 105 or n == 9:
            topic_slug, topic_name = "geography", "Geography"
        elif n in {2, 3, 4, 5, 6, 7, 8, 12, 19}:
            topic_slug, topic_name = "polity", "Polity"
        elif n in {71, 72, 73, 74, 75, 76, 77, 79, 107, 108, 109, 118}:
            topic_slug, topic_name = "economics", "Economics"
        else:
            topic_slug, topic_name = "current-affairs", "Current affairs (paper year)"
    fingerprint = hashlib.sha256(
        json.dumps(
            [subject, prompt.strip(), context, options, key.index], ensure_ascii=True
        ).encode()
    ).hexdigest()
    return {
        "id": str(uuid.uuid5(NAMESPACE, fingerprint)),
        "topic_slug": topic_slug,
        "topic_name": topic_name,
        "prompt": prompt.strip(),
        "context": context or None,
        "options": options,
        "correct_index": key.index,
        "explanation": key.explanation,
        "source_label": (
            f"UPSC CDS {paper.cycle} {paper.year} · Q{question.number} · "
            + {
                "official": "official answer key",
                "provisional": "provisional answer",
                "reviewed": "checked practice answer",
            }[key.basis]
        ),
        "difficulty": "cds-pyq",
        "is_active": True,
        "provenance": {
            "kind": "pyq",
            "import_batch": IMPORT_BATCH,
            "paper_question_id": question.id,
            "source_url": paper.source_url,
            "source_page_url": page,
            "answer_key_url": paper.answer_key_url,
            "answer_basis": key.basis,
            "year": paper.year,
            "cycle": paper.cycle,
            "number": question.number,
            "text_reviewed": bool(record.get("text_reviewed")),
        },
    }, "accepted"
