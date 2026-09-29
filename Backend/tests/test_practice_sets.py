import asyncio
import re
from unittest.mock import AsyncMock

import pytest

from app.main import app
from app.services.practice_sets import (
    PracticeQuestion,
    PracticeUnavailableError,
    generate_practice_set,
    topic_from_request,
)
from app.services.question_bank import BankQuery, question_context, resolve_query
from app.services.question_requests import requested_count, wants_practice
from app.services.rag import RagService, get_rag_service


def archive_context():
    return {
        "kind": "pyq",
        "query": vars(
            BankQuery(
                years=[], chapter="earth-interior", focus="volcanoes", subject="general-knowledge"
            )
        ),
        "questions": [],
        "returned": 1,
        "total": 1,
        "has_more": False,
    }


def sample_question(label):
    return {
        "prompt": f"Which process best describes {label}?",
        "options": ["A", "B", "C", "D"],
        "correct_index": 1,
        "explanation": "Option B explains this process correctly.",
    }


async def fake_generation(prompt, **kwargs):
    count = int(re.search(r"Create exactly (\d+)", prompt)[1])
    batch = int(re.search(r"Batch (\d+)", prompt)[1])
    return {"questions": [sample_question(f"batch {batch} concept {i}") for i in range(count)]}


@pytest.mark.parametrize(
    "question,count",
    [
        ("give me 50 questions related to that", 50),
        ("give me questions related to that topic , almost 50 questions", 50),
        ("generate fifty practice questions on volcanoes", 50),
        ("show next 50 PYQs", 50),
        ("Show me 500 questions", 500),
        ("give me all modern history PYQs", None),
    ],
)
def test_requested_quantity_is_not_limited_to_five(question, count):
    assert requested_count(question) == count


@pytest.mark.parametrize(
    "question,practice",
    [
        ("give me questions related to that topic , almost 50 questions", True),
        ("Give me 50 questions on volcanoes", True),
        ("ok now give me questions of geography related to volcanos", True),
        ("Give me 50 actual PYQs on volcanoes", False),
        ("Can you give me questions of modern history which came in cds?", False),
        ("Show next 50 PYQs", False),
        ("Give me all questions related to that topic", False),
        ("Explain the greenhouse effect", False),
        ("What is a volcano?", False),
        ("Why is the answer to question 50 B?", False),
        ("are there only these four questions? are you sure?", False),
        ("Generate similar practice questions like CDS PYQs", True),
    ],
)
def test_practice_archive_and_lesson_intents(question, practice):
    assert wants_practice(question, archive_context()) is practice


def test_topics_preserve_specificity_and_free_form_topics():
    assert (
        topic_from_request(
            "give me 50 questions related to that topic", [], archive_context(), None
        )
        == "Volcanoes"
    )
    assert (
        topic_from_request("Give me 50 questions on the solar system", [], None, None)
        == "the solar system"
    )
    assert "greenhouse effect" in topic_from_request(
        "Give me fifty questions", [("user", "Explain the greenhouse effect")], None, None
    )
    query = resolve_query("Give me all volcano PYQs", None)
    assert query.focus == "volcanoes" and query.limit == 50


@pytest.mark.parametrize(
    "question,topic",
    [
        ("Give me 50 biology questions", "biology"),
        ("quiz me on photosynthesis", "photosynthesis"),
        ("show me questions about cell division", "cell division"),
        ("Give me fifty algebra practice quesitons", "algebra"),
    ],
)
def test_new_freeform_topic_replaces_previous_practice_topic(question, topic):
    previous = {"kind": "practice", "topic": "Volcanoes"}
    assert topic_from_request(question, [], archive_context(), previous) == topic


def test_fifty_questions_are_generated_counted_and_validated():
    async def scenario():
        generator = AsyncMock(side_effect=fake_generation)
        result = await generate_practice_set(
            generator,
            "give me questions related to that topic , almost 50 questions",
            [],
            archive=archive_context(),
        )
        assert result["returned"] == result["requested"] == result["target"] == 50
        assert result["complete"] and len(result["questions"]) == 50
        assert [item["number"] for item in result["questions"]] == list(range(1, 51))
        assert generator.await_count == 1
        assert len({q["prompt"] for q in result["questions"]}) == 50
        assert all(len(q["options"]) == 4 for q in result["questions"])
        assert all("source_url" not in q for q in result["questions"])
        assert "batch 1 concept 49" in question_context("Explain question 50", result)

    asyncio.run(scenario())


def test_bulk_generation_is_bounded_and_not_exhaustive():
    async def scenario():
        for question in [
            "Give me 10000 questions on volcanoes",
            "Give me all questions on volcanoes",
        ]:
            generator = AsyncMock(side_effect=fake_generation)
            result = await generate_practice_set(generator, question, [])
            assert result["returned"] == 50 and generator.await_count == 1
            assert "limited to 50" in result["message"] or "no finite 'all'" in result["message"]

    asyncio.run(scenario())


def test_duplicate_and_malformed_items_are_not_counted_as_fifty():
    async def scenario():
        generator = AsyncMock(
            return_value={"questions": [sample_question("same topic")] * 10 + [{"prompt": "bad"}]}
        )
        result = await generate_practice_set(generator, "Give me 50 questions on volcanoes", [])
        assert result["returned"] == 1 and not result["complete"]
        assert "49 could not be completed" in result["message"]
        with pytest.raises(PracticeUnavailableError):
            await generate_practice_set(
                AsyncMock(return_value={"questions": [{"prompt": "bad"}]}),
                "Give me 10 questions on volcanoes",
                [],
            )

    asyncio.run(scenario())


def test_options_and_answer_indexes_are_checked():
    for changes in [
        {"options": ["A"] * 4},
        {"correct_index": 4},
        {"correct_index": True},
        {"options": ["", "B", "C", "D"]},
    ]:
        with pytest.raises(ValueError):
            PracticeQuestion.model_validate({**sample_question("a process"), **changes})


def test_partial_set_and_duplicate_are_repaired_to_requested_count():
    async def scenario():
        async def flaky_generation(prompt):
            batch = int(re.search(r"Batch (\d+)", prompt)[1])
            result = await fake_generation(prompt)
            if batch == 1:
                result["questions"] = result["questions"][:40]
                result["questions"][-1] = result["questions"][0]
            return result

        generator = AsyncMock(side_effect=flaky_generation)
        result = await generate_practice_set(generator, "Give me 50 questions on volcanoes", [])
        assert result["complete"] and result["returned"] == 50
        assert generator.await_count == 2
        repair = generator.call_args_list[-1].args[0]
        assert "Create exactly 11" in repair and "batch 1 concept 38" in repair

    asyncio.run(scenario())


def test_failed_primary_set_uses_at_most_two_repair_requests():
    async def scenario():
        async def flaky_generation(prompt):
            if "Batch 1:" in prompt:
                raise RuntimeError("Temporary provider failure")
            return await fake_generation(prompt)

        generator = AsyncMock(side_effect=flaky_generation)
        result = await generate_practice_set(generator, "Give me 50 questions on volcanoes", [])
        assert result["complete"] and result["returned"] == 50
        assert generator.await_count == 3

    asyncio.run(scenario())


def test_provider_limit_is_not_described_as_missing_paper_records():
    async def scenario():
        generator = AsyncMock(side_effect=RuntimeError("The AI provider is rate-limited."))
        with pytest.raises(PracticeUnavailableError, match="not a paper-archive limit"):
            await generate_practice_set(generator, "Give me 50 questions on volcanoes", [])
        assert generator.await_count == 3

    asyncio.run(scenario())


def test_missing_topic_clarifies_without_losing_requested_count():
    async def scenario():
        generator = AsyncMock(side_effect=fake_generation)
        clarification = await generate_practice_set(generator, "Give me 50 questions", [])
        assert clarification["kind"] == "clarification"
        generator.assert_not_called()
        assert wants_practice("volcanoes", practice_context=clarification)
        result = await generate_practice_set(generator, "volcanoes", [], previous=clarification)
        assert result["returned"] == 50

    asyncio.run(scenario())


def test_general_tutor_recovers_from_old_archive_only_refusal():
    async def scenario():
        service = RagService()
        service.retrieve = AsyncMock(return_value=[])
        service._generate_json = AsyncMock(
            side_effect=[
                {"answer": "I can only provide questions from stored paper records."},
                {"answer": "The greenhouse effect involves gases absorbing infrared radiation."},
            ]
        )
        result = await service.answer(
            None,
            "Explain greenhouse effect simply",
            None,
            [("assistant", "I cannot generate new questions.")],
        )
        assert "infrared" in result.answer and result.answer_kind == "explanation"
        assert service._generate_json.await_count == 2

    asyncio.run(scenario())


def test_practice_api_saves_fifty_questions_and_uses_them_in_followups(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Practice tester",
            "email": "practice-set@example.com",
            "password": "secure123",
        },
    )
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    service = RagService()
    service._generate_json = AsyncMock(side_effect=fake_generation)
    service.retrieve = AsyncMock(return_value=[])
    app.dependency_overrides[get_rag_service] = lambda: service
    try:
        response = client.post(
            "/api/v1/doubts/ask",
            headers=headers,
            json={
                "question": "Give me 50 questions on volcanoes",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["answer_kind"] == "practice" and data["practice_result"]["returned"] == 50
        assert data["pyq_result"] is None and not data["grounded"]
        saved = client.get(
            f"/api/v1/doubts/conversations/{data['conversation_id']}", headers=headers
        )
        assert len(saved.json()["messages"][-1]["practice_result"]["questions"]) == 50
        service._generate_json = AsyncMock(
            return_value={"answer": "Explanation of question fifty."}
        )
        explained = client.post(
            "/api/v1/doubts/ask",
            headers=headers,
            json={
                "question": "Explain question 50",
                "conversation_id": data["conversation_id"],
            },
        )
        assert explained.status_code == 200, explained.text
        assert "batch 1 concept 49" in service._generate_json.call_args.args[0]
        assert "NOT actual paper records" in service._generate_json.call_args.args[0]
    finally:
        app.dependency_overrides.pop(get_rag_service, None)
