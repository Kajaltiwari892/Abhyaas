import asyncio
from datetime import date
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.papers import PaperQuestion, PreviousPaper
from app.models.practice import Subject
from app.services.question_bank import (
    BankQuery,
    archive_discussion,
    classify_topics,
    is_archive_discussion,
    question_context,
    resolve_query,
    search_bank,
    text_checksum,
)
from app.services.rag import RagService, get_rag_service
from scripts.import_question_bank import prepare_record
from tests.test_practice_sets import fake_generation


def previous_earth_search():
    return {
        "kind": "pyq",
        "query": vars(
            BankQuery(years=[2026], chapter="earth-interior", subject="general-knowledge")
        ),
        "questions": [],
        "total": 4,
        "returned": 4,
        "has_more": False,
        "indexed_questions": 480,
        "catalog_questions": 1000,
    }


@pytest.mark.parametrize(
    "question",
    [
        "are there only these four questions? are you sure?",
        "are you sure these are actual CDS questions?",
        "Did these questions really appear in CDS?",
        "Are there any more?",
        "Why only four?",
        "Why is this response so fast? Is it static?",
    ],
)
def test_challenges_are_not_repeat_listing_commands(question):
    previous = previous_earth_search()
    assert is_archive_discussion(question, previous)
    assert resolve_query(question, None, previous) is None
    discussion = archive_discussion(question, previous)
    assert discussion["kind"] == "archive_info"
    assert "not a claim" in discussion["message"] and "480 of 1000" in discussion["message"]
    followup = resolve_query("only 2025", None, discussion)
    assert followup.chapter == "earth-interior" and followup.years == [2025]


@pytest.mark.parametrize(
    "question,chapter,terms",
    [
        ("can you give me all the pyq questions of history", "history", ""),
        ("now ancient history", "ancient-history", ""),
        ("give me geography pyqs", "geography", ""),
        ("Give me photosynthesis PYQs", None, "photosynthesis"),
        ("Show English PYQs", None, ""),
    ],
)
def test_topic_changes_replace_stale_chapter(question, chapter, terms):
    query = resolve_query(question, None, previous_earth_search())
    assert query and query.chapter == chapter and query.terms == terms
    assert query.offset == 0


@pytest.mark.parametrize(
    "question",
    [
        "What is history?",
        "Explain the first question",
        "Explain this PYQ",
        "Why is option B wrong in these questions?",
        "What are S-waves?",
        "How does photosynthesis work?",
        "Tell me about the interior of Earth",
        "What is the difference between weather and climate?",
        "Is the Earth crust solid?",
        "Give me a short summary of History",
        "List the types of rocks",
        "Books on history",
        "How many layers does the Earth have?",
    ],
)
def test_normal_subject_questions_stay_conversational(question):
    assert resolve_query(question, None, previous_earth_search()) is None


def test_history_tags_cover_periods_without_british_scientist_false_positive():
    assert "ancient-history" in classify_topics(
        {"prompt": "The Harappan civilization"}, "general-knowledge"
    )
    assert "medieval-history" in classify_topics(
        {"prompt": "Akbar and the Mughal empire"}, "general-knowledge"
    )
    assert "modern-history" in classify_topics(
        {"prompt": "The Quit India Movement"}, "general-knowledge"
    )
    assert "modern-history" not in classify_topics(
        {"prompt": "A British scientist discovered an electron"}, "general-knowledge"
    )


def test_followup_context_contains_real_question_and_not_unverified_key():
    previous = previous_earth_search()
    previous["questions"] = [
        {
            "number": 69,
            "prompt": "Actual volcanic cones question",
            "options": ["A", "B", "C", "D"],
            "answer_verified": False,
            "correct_index": None,
        },
        {"number": 33, "prompt": "Actual earthquake question", "options": ["A", "B", "C", "D"]},
    ]
    context = question_context("explain the first one", previous)
    assert "volcanic cones" in context and "earthquake question" not in context
    assert '"correct_index": null' in context
    assert "earthquake question" in question_context("solve Q33", previous)
    assert not question_context("What is photosynthesis?", previous)


def test_screenshot_conversation_then_lesson_uses_different_routes():
    async def scenario():
        async with SessionLocal() as db:
            await seed(db)
            service = RagService()
            service.retrieve = AsyncMock(return_value=[])
            service._generate_json = AsyncMock(
                return_value={"answer": "A subject explanation", "confidence": 0.5}
            )
            first = await service.answer(
                db, "can you give me earth's interior question pyq?", None, []
            )
            assert first.pyq_result["total"] == 4
            sure = await service.answer(
                db,
                "are there only these four questions? are you sure?",
                None,
                [],
                pyq_context=first.pyq_result,
            )
            assert sure.answer_kind == "archive_info" and sure.answer != first.answer
            history = await service.answer(
                db,
                "can you give me all the pyq questions of history",
                None,
                [],
                pyq_context=sure.pyq_result,
            )
            assert history.pyq_result["query"]["chapter"] == "history"
            assert not history.pyq_result[
                "questions"
            ]  # No history records in this fixture; never return Earth.
            service._generate_json.assert_not_called()
            lesson = await service.answer(
                db, "What is photosynthesis?", None, [], pyq_context=history.pyq_result
            )
            assert lesson.answer_kind == "explanation" and lesson.pyq_result is None
            service._generate_json.assert_awaited_once()
            await service.answer(
                db, "Explain the first one", None, [], pyq_context=first.pyq_result
            )
            prompt = service._generate_json.call_args.args[0]
            assert "Original earthquake question 1, 2026" in prompt
            assert '"correct_index": null' in prompt

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "spelling", ["interiro earth", "earth interiror", "interior of the earth", "Earth's interior"]
)
def test_misspelled_earth_chapter(spelling: str) -> None:
    query = resolve_query(f"Can you only give me {spelling} chapter pyq question here?", None)
    assert query and query.chapter == "earth-interior"
    assert query.subject == "general-knowledge"
    assert not query.needs_clarification


def test_year_cycle_and_context_preserved_without_leaking_into_new_lessons() -> None:
    query = resolve_query("Give me Earth interior CDS II 2026 PYQs", None)
    assert query and query.years == [2026] and query.cycle == "II"
    previous = {"query": vars(query), "returned": 5}
    followup = resolve_query("only 2025", None, previous)
    assert followup.years == [2025] and followup.chapter == "earth-interior"
    assert followup.cycle == "II"
    more = resolve_query("Show next PYQs", None, previous)
    assert more.offset == 5 and more.years == [2026]
    assert resolve_query("Explain the weather and climate chapter", None, previous) is None
    assert resolve_query("Generate similar practice questions", None, previous) is None


def test_ambiguous_year_asks_subject_and_then_uses_it() -> None:
    query = resolve_query("can you give me questions related to the question came in 2026?", None)
    assert query and query.needs_clarification and query.years == [2026]
    clarified = resolve_query("English", None, {"query": vars(query), "returned": 0})
    assert clarified.subject == "english" and clarified.years == [2026]
    assert not clarified.needs_clarification and not clarified.terms


def test_english_earthquake_sentence_is_not_geography() -> None:
    assert "earth-interior" not in classify_topics(
        {"prompt": "Find the error: earthquake survivors."}, "english"
    )
    assert "earth-interior" in classify_topics(
        {"prompt": "Consider the statements about earthquakes."}, "general-knowledge"
    )
    assert "earth-interior" not in classify_topics(
        {"prompt": "The atmosphere evolved from the hot interior of the Earth."},
        "general-knowledge",
    )


def test_review_is_invalidated_when_question_text_changes() -> None:
    key = "/papers/cds-i-2026/general-knowledge/page-1.webp#1"
    record = {"prompt": "Which layer?", "options": ["A", "B", "C", "D"]}
    reviews = {key: {"checksum": text_checksum(record), "topics": ["earth-interior"]}}
    assert prepare_record(key, record, "general-knowledge", reviews)["text_reviewed"]
    changed = prepare_record(
        key, {**record, "prompt": "Changed text"}, "general-knowledge", reviews
    )
    assert not changed["text_reviewed"]
    with pytest.raises(ValueError):
        prepare_record(key, {**record, "options": ["A"]}, "general-knowledge", {})


async def seed(db) -> None:
    subject = Subject(
        slug="general-knowledge", code="GK", name="General Knowledge", description="GK", position=1
    )
    for year in [2025, 2026]:
        paper = PreviousPaper(
            subject=subject,
            year=year,
            cycle="I",
            title=f"CDS I {year} GK",
            exam_date=date(year, 4, 12),
            duration_seconds=7200,
            total_marks=100,
            official_question_count=3,
            academy_tracks=["IMA"],
            source_url=f"https://upsc.gov.in/{year}.pdf",
        )
        for number in range(1, 4):
            paper.questions.append(
                PaperQuestion(
                    number=number,
                    prompt=f"Question {number}",
                    options=["A", "B", "C", "D"],
                    correct_index=2,
                    explanation="Key explanation",
                    source_label="UPSC",
                    is_verified=False,
                    transcription={
                        "prompt": f"Original earthquake question {number}, {year}.",
                        "options": ["Option A", "Option B", "Option C", "Option D"],
                        "topics": ["earth-interior"] if number < 3 else ["weather-climate"],
                        "source_page": 3,
                        "sourcePageUrl": "/papers/page-3.webp",
                        "text_reviewed": True,
                    },
                )
            )
        db.add(paper)
    await db.commit()


def test_exact_question_records_filters_pagination_and_no_llm() -> None:
    async def scenario():
        async with SessionLocal() as db:
            await seed(db)
            query = BankQuery(
                years=[2026], chapter="earth-interior", subject="general-knowledge", limit=1
            )
            first = await search_bank(db, query)
            assert first["total"] == 2 and first["returned"] == 1 and first["has_more"]
            card = first["questions"][0]
            assert card["prompt"] == "Original earthquake question 1, 2026."
            assert card["source_url"].endswith("2026.pdf#page=3")
            assert card["correct_index"] is None and card["text_reviewed"]
            query.offset = 1
            second = await search_bank(db, query)
            assert second["questions"][0]["id"] != card["id"] and not second["has_more"]
            service = RagService()
            service._generate_json = AsyncMock(
                side_effect=AssertionError("PYQs must not use AI generation")
            )
            result = await service.answer(db, "Give Earth interior 2026 CDS I PYQs", None, [])
            assert result.answer_kind == "pyq" and result.pyq_result["total"] == 2
            service._generate_json.assert_not_called()
            missing = await service.answer(db, "Give Earth interior 2030 PYQs", None, [])
            assert not missing.pyq_result["questions"]
            assert "does not mean UPSC never asked" in missing.answer
            assert not missing.sources

    asyncio.run(scenario())


def test_generated_practice_is_explicitly_not_pyqs() -> None:
    async def scenario():
        service = RagService()
        service._generate_json = AsyncMock(side_effect=fake_generation)
        result = await service.answer(
            None, "Generate similar practice questions on Earth interior", None, []
        )
        assert result.answer_kind == "practice" and result.pyq_result is None
        assert result.practice_result["returned"] == 10 and not result.sources
        assert "not actual CDS PYQs" in result.answer

    asyncio.run(scenario())


def test_bulk_archive_counts_all_shortfall_and_specific_focus():
    async def scenario():
        async with SessionLocal() as db:
            await seed(db)
            paper = await db.scalar(select(PreviousPaper).where(PreviousPaper.year == 2026))
            for number in range(4, 64):
                db.add(
                    PaperQuestion(
                        paper_id=paper.id,
                        number=number,
                        prompt=f"Record {number}",
                        options=["A", "B", "C", "D"],
                        correct_index=0,
                        explanation="",
                        source_label="UPSC",
                        is_verified=False,
                        transcription={
                            "prompt": f"Original volcanic lava question {number}",
                            "options": ["A", "B", "C", "D"],
                            "topics": ["earth-interior"],
                        },
                    )
                )
            await db.commit()
            query = resolve_query("Give me 50 actual volcano PYQs", None)
            first = await search_bank(db, query)
            assert first["total"] == 60 and first["returned"] == 50
            assert first["has_more"] and first["shortfall"] == 0
            assert all("volcanic" in card["prompt"] for card in first["questions"])
            following = resolve_query("Show next 50 PYQs", None, first)
            second = await search_bank(db, following)
            assert second["returned"] == 10 and second["shortfall"] == 40
            assert not {q["id"] for q in first["questions"]} & {
                q["id"] for q in second["questions"]
            }
            assert "requested 50 actual PYQs" in second["message"]
            all_year = resolve_query("Give me all Earth interior 2025 PYQs", None)
            all_result = await search_bank(db, all_year)
            assert all_result["returned"] == all_result["total"] == 2
            assert "All current matches" in all_result["message"]
            assert resolve_query("show all", None, first).limit == 50
            assert (
                resolve_query("give me all questions related to that topic", None, first).focus
                == "volcanoes"
            )

    asyncio.run(scenario())


def test_api_preserves_structured_questions_and_followup_filters(client) -> None:
    async def setup():
        async with SessionLocal() as db:
            await seed(db)

    asyncio.run(setup())
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Bank test",
            "email": "bank@example.com",
            "password": "secure123",
        },
    )
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    service = RagService()
    service._generate_json = AsyncMock(side_effect=AssertionError("No generation for PYQs"))
    app.dependency_overrides[get_rag_service] = lambda: service
    try:
        first = client.post(
            "/api/v1/doubts/ask",
            headers=headers,
            json={
                "question": "Can you only give me interiro earth chapter pyq question here?",
            },
        )
        assert first.status_code == 200, first.text
        data = first.json()
        assert data["answer_kind"] == "pyq" and data["pyq_result"]["total"] == 4
        followup = client.post(
            "/api/v1/doubts/ask",
            headers=headers,
            json={
                "question": "only 2026",
                "conversation_id": data["conversation_id"],
            },
        )
        assert followup.status_code == 200, followup.text
        assert followup.json()["pyq_result"]["total"] == 2
        assert all(q["year"] == 2026 for q in followup.json()["pyq_result"]["questions"])
        saved = client.get(
            f"/api/v1/doubts/conversations/{data['conversation_id']}", headers=headers
        )
        assert saved.status_code == 200
        assert saved.json()["messages"][-1]["pyq_result"]["query"]["years"] == [2026]
        sure = client.post(
            "/api/v1/doubts/ask",
            headers=headers,
            json={
                "question": "are you sure these are actual CDS questions?",
                "conversation_id": data["conversation_id"],
            },
        )
        assert sure.status_code == 200, sure.text
        assert sure.json()["answer_kind"] == "archive_info"
        switched = client.post(
            "/api/v1/doubts/ask",
            headers=headers,
            json={
                "question": "give me all history pyqs",
                "conversation_id": data["conversation_id"],
            },
        )
        assert switched.status_code == 200, switched.text
        assert switched.json()["pyq_result"]["query"]["chapter"] == "history"
        assert not switched.json()["pyq_result"]["questions"]
        paper_id = data["pyq_result"]["questions"][0]["paper_id"]
        paper = client.get(f"/api/v1/papers/{paper_id}", headers=headers).json()
        assert paper["questions"][0]["prompt"] == data["pyq_result"]["questions"][0]["prompt"]
    finally:
        app.dependency_overrides.pop(get_rag_service, None)
