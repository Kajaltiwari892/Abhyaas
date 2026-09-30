from types import SimpleNamespace

import pytest

from app.services.practice_catalog import prepare_question


def source_record(**changes):
    paper = SimpleNamespace(
        is_published=True,
        source_url="https://upsc.gov.in/paper.pdf",
        answer_key_url="https://upsc.gov.in/key.pdf",
        year=2025,
        cycle="II",
    )
    record = {
        "prompt": "Which statement about photosynthesis is correct?",
        "options": ["a", "b", "c", "d"],
        "sourcePageUrl": "/papers/cds-ii-2025/general-knowledge/page-1.webp",
        **changes,
    }
    question = SimpleNamespace(
        id="source-q",
        number=41,
        is_verified=True,
        source_label="Official UPSC final key",
        correct_index=2,
        explanation="Official answer C",
        transcription=record,
    )
    return question, paper


def test_import_preserves_provenance_and_has_stable_content_id():
    q, p = source_record()
    first, reason = prepare_question(q, p, "general-knowledge")
    assert reason == "accepted" and first["topic_slug"] == "general-science"
    assert first["provenance"]["text_reviewed"] is False
    assert first["provenance"]["source_url"] == p.source_url
    assert prepare_question(q, p, "general-knowledge")[0]["id"] == first["id"]
    q.transcription["prompt"] += " Explain."
    assert prepare_question(q, p, "general-knowledge")[0]["id"] != first["id"]


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"hasVisual": True}, "visual_question"),
        ({"options": ["a", "b"]}, "incomplete_options"),
        ({"options": ["a", "a", "c", "d"]}, "invalid_options_or_key"),
        ({"directions": "Choose the meaning of the underlined word"}, "missing_underlined_target"),
        ({"prompt": "Which of the statements given above are correct?"}, "missing_context"),
        ({"prompt": "Select the correct option:"}, "missing_context"),
        ({"prompt": "Question 34 is missing from the provided image source."}, "missing_text"),
        ({"prompt": "Match List-I with List-II and select the answer"}, "missing_lists"),
        ({"sourcePageUrl": "https://evil.example/x"}, "missing_source_page"),
    ],
)
def test_incomplete_questions_never_enter_scored_practice(change, reason):
    q, p = source_record(**change)
    assert prepare_question(q, p, "general-knowledge") == (None, reason)


def test_provisional_or_unverified_key_is_excluded():
    q, p = source_record()
    p.answer_key_url = "https://upsc.gov.in/provisional-key.pdf"
    assert prepare_question(q, p, "general-knowledge")[0] is None
    p.answer_key_url = "https://upsc.gov.in.attacker.test/key.pdf"
    assert prepare_question(q, p, "general-knowledge")[0] is None


def test_complete_question_in_directions_is_supported():
    q, p = source_record(
        prompt="Select the correct option:",
        directions=(
            "Consider the following statements about earthquakes.\n"
            "1. Richter scale measures magnitude.\n"
            "2. Seismic waves originate at the focus.\nWhich are correct?"
        ),
    )
    assert prepare_question(q, p, "general-knowledge")[1] == "accepted"
