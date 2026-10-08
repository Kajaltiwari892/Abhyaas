import asyncio
from types import SimpleNamespace

import pytest

from app.models.papers import PaperQuestion
from app.services.paper_answer_review import review_batch
from app.services.paper_answers import save_review, stored_answer


def question(number=1):
    return PaperQuestion(
        paper_id="paper",
        number=number,
        prompt="What is 2 + 2?",
        context=None,
        options=["1", "2", "4", "5"],
        correct_index=0,
        explanation="Pending",
        source_label="Paper scan",
        is_verified=False,
        transcription={"prompt": "What is 2 + 2?", "options": ["1", "2", "4", "5"]},
    )


@pytest.mark.parametrize(
    "second_status,second_index,approved",
    [("solved", 2, True), ("solved", 1, False), ("uncertain", None, False)],
)
def test_independent_review_requires_agreement_without_leaking_candidate(
    second_status, second_index, approved
):
    q = question()
    paper = SimpleNamespace(
        year=2026,
        cycle="I",
        source_checksum=None,
        source_url="https://upsc.gov.in/paper.pdf",
        subject=SimpleNamespace(slug="english"),
    )
    prompts = []

    async def generate(prompt, count):
        prompts.append(prompt)
        return {
            "solutions": [
                {
                    "number": 1,
                    "status": "solved" if len(prompts) == 1 else second_status,
                    "answer_index": 2 if len(prompts) == 1 else second_index,
                    "explanation": "Adding two and two yields four, so the answer is C.",
                }
            ]
        }

    result = asyncio.run(review_batch(paper, [q], generate, apply=True))
    assert result["saved"] == int(approved)
    assert (stored_answer(q) is not None) == approved
    assert '"correct_index"' not in prompts[1]
    assert "Adding two and two" not in prompts[1]
    assert q.is_verified is False


def test_placeholder_indices_and_invalid_review_never_score():
    q = question()
    assert stored_answer(q) is None
    for index in [True, -1, 4, "2"]:
        with pytest.raises(ValueError):
            save_review(
                q,
                index,
                "The answer is four after adding the two numbers.",
                method="editorial",
                evidence={"checked": True},
            )
    save_review(
        q,
        2,
        "The answer is four after adding the two numbers.",
        method="editorial",
        evidence={"checked": True},
    )
    q.answer_review = dict(q.answer_review, status="candidate")
    assert stored_answer(q) is None


def test_official_answer_wins_and_cannot_be_overwritten():
    q = question()
    save_review(
        q,
        2,
        "The answer is four after adding the two numbers.",
        method="editorial",
        evidence={"checked": True},
    )
    q.is_verified = True
    q.correct_index = 1
    assert stored_answer(q).index == 1
    with pytest.raises(ValueError, match="overwrite"):
        save_review(
            q,
            2,
            "This must not overwrite an official key.",
            method="editorial",
            evidence={"checked": True},
        )


def test_first_pass_or_provider_failure_saves_nothing():
    q = question()
    paper = SimpleNamespace(
        year=2026,
        cycle="I",
        source_checksum=None,
        source_url="https://upsc.gov.in/paper.pdf",
        subject=SimpleNamespace(slug="english"),
    )
    calls = 0

    async def generate(prompt, count):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Provider unavailable")
        return {
            "solutions": [
                {
                    "number": 1,
                    "status": "solved",
                    "answer_index": 2,
                    "explanation": "Adding two and two gives four, which is C.",
                }
            ]
        }

    with pytest.raises(RuntimeError):
        asyncio.run(review_batch(paper, [q], generate, apply=True))
    assert q.answer_review is None and stored_answer(q) is None


@pytest.mark.parametrize("missing", ["diagram", "underlined", "passage", "options"])
def test_incomplete_source_cannot_be_approved_by_ai(missing):
    q = question()
    paper = SimpleNamespace(
        year=2026,
        cycle="I",
        source_checksum=None,
        source_url="https://upsc.gov.in/paper.pdf",
        subject=SimpleNamespace(slug="english"),
    )
    record = dict(q.transcription)
    if missing == "diagram":
        record["hasVisual"] = True
    elif missing == "underlined":
        record["directions"] = "Select the antonym of the underlined word."
    elif missing == "passage":
        record["directions"] = "Answer from the following passage."
    else:
        record["options"] = ["A", "B", "C", "D"]
    q.transcription = record

    async def generate(prompt, count):
        pytest.fail("Incomplete questions must not be sent to the AI")

    result = asyncio.run(review_batch(paper, [q], generate, apply=True))
    assert result["missing_text"] == 1 and result["saved"] == 0
    assert stored_answer(q) is None
