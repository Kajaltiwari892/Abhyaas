"""Shared intent/count rules: archive provenance is opt-in, not a tutor-wide restriction."""

import re

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "ten": 10,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "hundred": 100,
}


def normalized_request(question: str) -> str:
    """Normalize common typing slips without fuzzy-matching academic topic words."""
    clean = question.lower().strip()
    clean = re.sub(r"\b(?:quesitons|quesions|questons)\b", "questions", clean)
    clean = re.sub(r"\b(?:quesiton|quesion|queston)\b", "question", clean)
    return re.sub(r"\s+", " ", clean).strip(" ?.!")


def next_page_request(question: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:please )?(?:(?:show|give)(?: me)? )?(?:the )?"
            r"(?:next|more)(?: \d+)?(?: (?:pyqs?|questions?|page))?(?: please)?",
            normalized_request(question),
        )
    )


def refers_to_all_previous(question: str) -> bool:
    """Only an actual continuation inherits PYQ mode, not every request with 'all'."""
    clean = normalized_request(question)
    return bool(
        re.fullmatch(
            r"(?:please )?(?:(?:give|show|list|fetch)(?: me)? )?"
            r"(?:all|every|(?:the )?complete (?:set|list)|(?:the )?entire set)"
            r"(?: (?:the|these|those|remaining))?(?: questions?| pyqs?)?"
            r"(?: (?:related to|on|about|from) (?:this|that|the same) topic)?(?: please)?",
            clean,
        )
        or re.fullmatch(r"(?:show |give me )?all (?:these|those|them)", clean)
    )


def requested_count(question: str) -> int | None:
    clean = normalized_request(question)
    if re.match(r"^(?:are|is|were|was|did|why|how|what)\b", clean) and not re.search(
        r"\b(?:give|generate|create|make|prepare)\b", clean
    ):
        return None
    for word, number in NUMBER_WORDS.items():
        clean = re.sub(r"\b" + word + r"\b", str(number), clean)
    match = re.search(
        r"\b(\d{1,6})\s*(?:more\s+)?(?:practice\s+|original\s+|actual\s+)?"
        r"(?:questions?|mcqs?|pyqs?)\b",
        clean,
    )
    if not match:
        match = re.search(
            r"\b(?:give|show|list|generate|create|make|prepare|provide|want|need|have|next|first)\s+"
            r"(?:me\s+)?(?:almost\s+|about\s+|around\s+)?(\d{1,6})\b",
            clean,
        )
    return max(1, int(match[1])) if match else None


def explicit_archive(question: str) -> bool:
    # 'Original practice' asks for newly authored questions, not original paper records.
    question = re.sub(r"\boriginal\s+(?=practice\b)", "", question, flags=re.I)
    return bool(
        re.search(
            r"\bpyqs?\b|previous[- ]year|past (?:paper|exam)|"
            r"\b(?:questions?|papers?)\b.*\b(?:came|asked|appeared|actual|official|original|20\d{2})\b|"
            r"\b(?:actual|official|original|20\d{2})\b.*\b(?:questions?|papers?)\b",
            question,
            re.I,
        )
    )


def wants_all(question: str) -> bool:
    return bool(
        re.search(r"\b(?:all|every|complete set|complete list|entire set)\b", question, re.I)
    )


def wants_practice(
    question: str, archive_context: dict | None = None, practice_context: dict | None = None
) -> bool:
    clean = normalized_request(question)
    if (
        practice_context
        and practice_context.get("kind") == "clarification"
        and not re.search(r"\b(?:explain|what|why|how|solve|pyqs?|paper)\b", clean)
    ):
        return True
    original_practice = bool(re.search(r"\b(?:practice|similar|quiz me|mock test)\b", clean))
    provenance_text = re.sub(r"\boriginal\s+(?=practice\b)", "", clean)
    strict = bool(re.search(r"\b(?:actual|official|original|only)\b", provenance_text))
    if explicit_archive(clean) and not (original_practice and not strict):
        return False
    if re.search(r"\b(?:explain|solve|why|answer|correct|wrong)\b", clean) and not re.search(
        r"\b(?:give|generate|create|make|prepare|quiz)\b", clean
    ):
        return False
    if (
        archive_context
        and not original_practice
        and (
            (refers_to_all_previous(clean) and not requested_count(clean))
            or next_page_request(clean)
        )
    ):
        return False
    return bool(
        re.search(r"\bquiz me\b", clean)
        or (
            re.search(r"\b(?:questions|mcqs|quiz|test)\b", clean)
            and (
                original_practice
                or requested_count(clean)
                or re.search(
                    r"\b(?:give|show|list|generate|create|make|prepare|want|need|some)\b", clean
                )
            )
        )
        or (practice_context and next_page_request(clean))
    )
