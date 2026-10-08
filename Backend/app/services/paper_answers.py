"""One answer resolver for results, practice, the notebook and the tutor.

Pending scan records contain a legacy placeholder index (usually zero). That is
NEVER an answer. Only an existing verified key or a checked, text-bound review
can be used. Official keys take priority over our independently checked answers.
"""

import hashlib
import json
from dataclasses import dataclass
from urllib.parse import urlparse

from app.models.papers import PaperAnswer, PaperAttempt, PaperQuestion, PreviousPaper


@dataclass(frozen=True)
class StoredAnswer:
    index: int
    explanation: str
    source_label: str
    basis: str  # official, provisional, reviewed


def question_content_fingerprint(question: PaperQuestion) -> str:
    """Portable text hash for a manifest already bound to the source PDF checksum."""
    record = question.transcription or {}
    value = [
        question.number,
        record.get("prompt", question.prompt),
        record.get("options", question.options),
        question.context,
        record.get("directions"),
        record.get("passage"),
        record.get("sectionTitle"),
        record.get("hasVisual", False),
    ]
    return hashlib.sha256(json.dumps(value, ensure_ascii=True).encode()).hexdigest()


def question_fingerprint(question: PaperQuestion) -> str:
    """Bind a stored review to both the database paper and its exact question text."""
    return hashlib.sha256(
        f"{question.paper_id}:{question_content_fingerprint(question)}".encode()
    ).hexdigest()


def stored_answer(
    question: PaperQuestion, paper: PreviousPaper | None = None
) -> StoredAnswer | None:
    options = (question.transcription or {}).get("options", getattr(question, "options", []))
    if not isinstance(options, list) or not 2 <= len(options) <= 10:
        return None
    if question.is_verified and type(question.correct_index) is int:
        if not 0 <= question.correct_index < len(options):
            return None
        # Preserve legacy verified keys. Provisional keys must never be called final.
        url = urlparse(paper.answer_key_url or "") if paper else None
        basis = (
            "provisional"
            if paper and "prov" in (paper.answer_key_url or "").lower()
            else "reviewed"
            if paper
            and not (
                url and url.hostname in {"upsc.gov.in", "www.upsc.gov.in"} and url.scheme == "https"
            )
            else "official"
        )
        label = question.source_label if basis != "reviewed" else "Checked practice answer"
        return StoredAnswer(question.correct_index, question.explanation, label, basis)
    review = getattr(question, "answer_review", None)
    if not isinstance(review, dict) or review.get("status") != "reviewed":
        return None
    index = review.get("correct_index")
    if (
        type(index) is not int
        or not 0 <= index < len(options)
        or review.get("fingerprint") != question_fingerprint(question)
        or review.get("method") not in {"editorial", "independent_ai"}
        or not isinstance(review.get("explanation"), str)
        or len(review["explanation"].strip()) < 10
    ):
        return None
    return StoredAnswer(
        index,
        review["explanation"],
        str(review.get("source_label") or "Checked practice answer"),
        "reviewed",
    )


def save_review(
    question: PaperQuestion, index: int, explanation: str, *, method: str, evidence: dict
) -> None:
    if question.is_verified:
        raise ValueError("An independent review cannot overwrite an existing verified key")
    options = (question.transcription or {}).get("options", question.options)
    if (
        not isinstance(options, list)
        or not 2 <= len(options) <= 10
        or type(index) is not int
        or not 0 <= index < len(options)
    ):
        raise ValueError("Invalid answer option")
    if (
        method not in {"editorial", "independent_ai"}
        or not isinstance(explanation, str)
        or not 10 <= len(explanation.strip()) <= 6000
    ):
        raise ValueError("An answer needs a checked explanation")
    if not evidence:
        raise ValueError("An answer needs its review evidence")
    question.answer_review = {
        "status": "reviewed",
        "correct_index": index,
        "explanation": explanation.strip(),
        "method": method,
        "source_label": "AI-checked practice answer"
        if method == "independent_ai"
        else "Checked practice answer",
        "fingerprint": question_fingerprint(question),
        "evidence": evidence,
    }


def grade_paper(
    paper: PreviousPaper, questions: list[PaperQuestion], answers: list[PaperAnswer]
) -> dict:
    keys = {q.id: key for q in questions if (key := stored_answer(q, paper)) is not None}
    question_ids = {q.id for q in questions}
    choices = {
        answer.question_id: answer.selected_index
        for answer in answers
        if answer.question_id in question_ids
    }
    correct = sum(choices.get(qid) == key.index for qid, key in keys.items())
    incorrect = sum(qid in choices and choices[qid] != key.index for qid, key in keys.items())
    marks = paper.total_marks / paper.official_question_count
    return {
        "keys": keys,
        "choices": choices,
        "correct": correct,
        "incorrect": incorrect,
        "score": round((correct - incorrect * paper.negative_mark_fraction) * marks, 2)
        if keys
        else None,
        "max_score": round(len(keys) * marks, 2) if keys else None,
        "official": sum(k.basis == "official" for k in keys.values()),
        "reviewed": sum(k.basis == "reviewed" for k in keys.values()),
        "provisional": sum(k.basis == "provisional" for k in keys.values()),
    }


def refresh_attempt_grade(
    attempt: PaperAttempt,
    paper: PreviousPaper,
    questions: list[PaperQuestion],
    answers: list[PaperAnswer],
) -> dict:
    grade = grade_paper(paper, questions, answers)
    attempt.correct_answers = grade["correct"]
    attempt.scored_questions = len(grade["keys"])
    attempt.score = grade["score"]
    for answer in answers:
        key = grade["keys"].get(answer.question_id)
        answer.is_correct = bool(key and answer.selected_index == key.index)
    return grade
