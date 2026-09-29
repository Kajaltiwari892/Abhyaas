"""Regression cases for natural tutor requests after a source-linked PYQ lookup."""

import pytest

from app.services.question_bank import BankQuery, archive_discussion, resolve_query
from app.services.question_requests import requested_count, wants_practice


def volcano_archive():
    return {
        "kind": "pyq",
        "query": vars(
            BankQuery(
                years=[],
                subject="general-knowledge",
                chapter="earth-interior",
                focus="volcanoes",
            )
        ),
        "returned": 10,
        "total": 20,
        "has_more": True,
    }


@pytest.mark.parametrize(
    "question",
    [
        "Show me questions on biology",
        "Show me all physics questions",
        "List all questions on climate",
        "Give me all questions on photosynthesis",
        "Give me original practice questions on history",
        "Can you give me 50 quesitons about volcanoes?",
    ],
)
def test_new_practice_requests_do_not_inherit_old_archive_restriction(question):
    assert wants_practice(question, volcano_archive())


def test_requested_count_tolerates_common_question_typo():
    assert requested_count("I need 50 quesitons about volcanoes") == 50


@pytest.mark.parametrize(
    "question",
    [
        "I need 50 physics questions",
        "I want 50 biology questions",
        "Prepare 50 geography questions",
        "Can I have 50 history questions?",
    ],
)
def test_count_before_freeform_topic_is_respected(question):
    assert requested_count(question) == 50


@pytest.mark.parametrize(
    "question",
    [
        "Give me the next 20 questions please",
        "Please show me the next 20 questions!",
        "Show next page",
        "next 20 questions?",
    ],
)
def test_polite_next_page_requests_keep_archive_and_advance(question):
    previous = volcano_archive()
    assert not wants_practice(question, previous)
    query = resolve_query(question, None, previous)
    assert query and query.offset == 10 and query.focus == "volcanoes"
    assert query.limit == (20 if "20" in question else 10)


@pytest.mark.parametrize(
    "question",
    [
        "Give me all questions related to that topic",
        "Show me all the questions",
        "Give me all these",
        "Show the complete list",
    ],
)
def test_all_previous_stays_archive_without_inventing_more_questions(question):
    previous = volcano_archive()
    assert not wants_practice(question, previous)
    query = resolve_query(question, None, previous)
    assert query and query.focus == "volcanoes" and query.limit == 50
    assert query.offset == 0


@pytest.mark.parametrize("question", ["Give me photosynthesis PYQs", "all chapters"])
def test_new_archive_topic_and_clear_chapter_remove_stale_volcano_filter(question):
    query = resolve_query(question, None, volcano_archive())
    assert query and query.chapter is None and query.focus is None
    assert query.terms == ("photosynthesis" if "photosynthesis" in question else "")


def test_archive_coverage_reply_uses_specific_focus_not_parent_chapter():
    result = archive_discussion("Are there only these questions?", volcano_archive())
    assert "for Volcanoes" in result["message"]
    assert "not a claim" in result["message"]


@pytest.mark.parametrize(
    "question",
    [
        "Explain the greenhouse effect simply",
        "Why are these questions so difficult?",
        "Can you explain all of photosynthesis?",
        "What is the difference between lava and magma?",
    ],
)
def test_normal_lessons_never_become_practice_or_repeat_pyq_cards(question):
    previous = volcano_archive()
    assert not wants_practice(question, previous)
    assert resolve_query(question, None, previous) is None
