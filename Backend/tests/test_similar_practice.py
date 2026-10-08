import asyncio
import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models.practice import PracticeAttempt, Question, Topic
from app.models.rag import DoubtStudyProfile
from app.services.rag import RagUnavailableError, get_rag_service
from tests.test_practice import auth_headers, seed_catalog

ENDPOINT = "/api/v1/practice/attempts/similar"


class PracticeGenerator:
    def __init__(self):
        self.calls = []
        self.batch = 0
        self.broken = False
        self.repeat = False

    async def generate_similar_questions(self, prompt, topics):
        self.calls.append((prompt, topics))
        count = int(re.search(r"Create exactly (\d+)", prompt)[1])
        if self.broken:
            return {"questions": [{"prompt": "Invalid", "topic_slug": topics[0]}]}
        if not self.repeat:
            self.batch += 1
        return {
            "questions": [
                {
                    "prompt": f"Choose the grammatically correct sentence, item {self.batch}-{i}.",
                    "options": [
                        "Neither are ready.",
                        "Neither is ready.",
                        "Neither were ready.",
                        "Neither have ready.",
                    ],
                    "correct_index": 1,
                    "explanation": "Neither takes a singular verb when used as the subject here.",
                    "topic_slug": topics[0],
                }
                for i in range(count)
            ]
        }

    async def review_similar_questions(self, questions, *, focus_detail=None):
        return {
            "reviews": [
                {"number": i, "usable": True, "answer_index": q["correct_index"]}
                for i, q in enumerate(questions, start=1)
            ]
        }


@pytest.fixture
def generator(clean_database):
    asyncio.run(seed_catalog())
    fake = PracticeGenerator()
    app.dependency_overrides[get_rag_service] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_rag_service, None)


def start(client, headers, count=10, **extra):
    return client.post(
        ENDPOINT,
        headers=headers,
        json={"subject_slug": "english", "question_count": count, **extra},
    )


def test_later_provider_failure_preserves_reviewed_questions_for_repair(client, generator):
    headers = auth_headers(client)
    generate = generator.generate_similar_questions
    generation_calls = 0

    async def intermittent_generation(prompt, topics):
        nonlocal generation_calls
        generation_calls += 1
        if generation_calls == 2:
            generator.calls.append((prompt, topics))
            raise RagUnavailableError("Temporary provider failure")
        return await generate(prompt, topics)

    generator.generate_similar_questions = intermittent_generation
    response = start(client, headers, 50, topic_slug="grammar")
    assert response.status_code == 201, response.text
    assert len(response.json()["questions"]) == 50
    assert len(generator.calls) == 3
    assert [int(re.search(r"Create exactly (\d+)", p)[1]) for p, _ in generator.calls] == [
        25,
        25,
        25,
    ]


def test_full_50_question_set_is_private_saved_resumable_and_scored(client, generator):
    headers = auth_headers(client)
    before = client.get("/api/v1/catalog/questions?subject_slug=english").json()
    response = start(client, headers, 50, topic_slug="grammar")
    assert response.status_code == 201, response.text
    attempt = response.json()
    assert attempt["question_mode"] == "similar" and len(attempt["questions"]) == 50
    assert attempt["duration_seconds"] == 3000 and attempt["new_questions"] == 50
    assert len({q["id"] for q in attempt["questions"]}) == 50
    assert all("correct_index" not in q and "explanation" not in q for q in attempt["questions"])
    assert all(
        q["provenance"] == {"kind": "generated", "answer_verified": False}
        for q in attempt["questions"]
    )
    assert all(q["source_label"] == "AI-created CDS-style practice" for q in attempt["questions"])
    assert "not a beginner quiz" in generator.calls[0][0]
    assert len(generator.calls) == 2
    assert all("Create exactly 25" in prompt for prompt, _ in generator.calls)
    assert "Do not repeat:" in generator.calls[1][0]
    base = f"/api/v1/practice/attempts/{attempt['id']}"
    answer = {"question_id": attempt["questions"][0]["id"], "selected_index": 1}
    assert client.get(f"{base}/result", headers=headers).status_code == 409
    assert (
        client.patch(
            base,
            headers=headers,
            json={"duration_seconds": 75, "current_position": 2, "answers": [answer]},
        ).status_code
        == 200
    )
    resumed = client.get(base, headers=headers).json()
    assert resumed["elapsed_seconds"] == 75 and resumed["current_position"] == 2
    assert resumed["questions"] == attempt["questions"]
    assert "is_correct" not in resumed["answers"][0]
    result = client.post(
        f"{base}/complete", headers=headers, json={"duration_seconds": 90, "answers": [answer]}
    ).json()
    assert result["question_mode"] == "similar"
    assert result["correct_answers"] == 1 and len(result["review"]) == 50
    assert result["review"][0]["correct_index"] == 1
    assert client.get(f"{base}/result", headers=headers).json() == result
    history = client.get("/api/v1/practice/attempts", headers=headers).json()
    assert history["items"][0]["question_mode"] == "similar"
    assert client.get("/api/v1/catalog/questions?subject_slug=english").json() == before
    assert client.get("/api/v1/catalog/subjects").json()[0]["question_count"] == 3
    assert client.get(
        "/api/v1/practice/availability?subject_slug=english", headers=headers
    ).json() == {"total": 3, "seen": 0, "unseen": 3}
    bank = client.post(
        "/api/v1/practice/attempts",
        headers=headers,
        json={"subject_slug": "english", "question_count": 50},
    ).json()
    assert len(bank["questions"]) == 3 and bank["question_mode"] == "bank"
    other = client.post(
        "/api/v1/auth/register",
        json={"name": "Other", "email": "other@example.com", "password": "secure123"},
    ).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.get(base, headers=other_headers).status_code == 404
    assert client.get(f"{base}/result", headers=other_headers).status_code == 404
    assert (
        client.post(
            f"{base}/complete", headers=other_headers, json={"duration_seconds": 1}
        ).status_code
        == 404
    )
    # Wrong/skipped AI items retain their label in the notebook, not an official-paper label.
    notebook = client.get("/api/v1/notebook", headers=headers)
    assert notebook.status_code == 200, notebook.text
    assert all(
        item["source_label"] == "AI-created CDS-style practice" for item in notebook.json()["items"]
    )


def test_similar_practice_works_even_when_topic_has_no_bank_questions(client, generator):
    async def add_empty():
        async with SessionLocal() as db:
            topic = await db.scalar(select(Topic).where(Topic.slug == "grammar"))
            db.add(Topic(subject_id=topic.subject_id, slug="idioms", name="Idioms"))
            await db.commit()

    asyncio.run(add_empty())
    headers = auth_headers(client)
    response = start(client, headers, 10, topic_slug="idioms")
    assert response.status_code == 201 and len(response.json()["questions"]) == 10
    assert generator.calls[0][1] == ["idioms"]


def test_count_topic_and_auth_validation_happen_before_provider_calls(client, generator):
    headers = auth_headers(client)
    for count in [0, 51, 120, 10000]:
        assert start(client, headers, count).status_code == 422
    assert start(client, {}, 10).status_code == 401
    assert start(client, headers, topic_slug="wrong").status_code == 404
    assert start(client, headers, subject_slug="missing").status_code == 404
    assert generator.calls == []


def test_provider_quota_is_not_described_as_a_shortage_of_questions(client, generator):
    headers = auth_headers(client)

    async def throttled(prompt, topics):
        raise RagUnavailableError("The AI provider is rate-limited")

    generator.generate_similar_questions = throttled
    response = start(client, headers, 50)
    assert response.status_code == 503
    assert "AI usage limit" in response.json()["detail"]
    assert "Unanswered questions or Mixed revision" in response.json()["detail"]
    assert client.get("/api/v1/practice/attempts", headers=headers).json()["total"] == 0


def test_partial_or_invalid_sets_are_not_saved_and_busy_lock_is_released(client, generator):
    headers = auth_headers(client)
    generator.broken = True
    response = start(client, headers, 50)
    assert response.status_code == 503
    assert client.get("/api/v1/practice/attempts", headers=headers).json()["total"] == 0

    async def check():
        async with SessionLocal() as db:
            assert await db.scalar(select(func.count(Question.id))) == 3
            profile = await db.scalar(select(DoubtStudyProfile))
            assert profile.busy_until is None

    asyncio.run(check())
    generator.broken = False
    assert start(client, headers).status_code == 201


def test_exact_repeats_across_similar_sets_are_refused_not_resold_as_new(client, generator):
    headers = auth_headers(client)
    first = start(client, headers)
    assert first.status_code == 201
    generator.repeat = True
    assert start(client, headers).status_code == 503
    assert client.get("/api/v1/practice/attempts", headers=headers).json()["total"] == 1
    assert "Choose the grammatically" in generator.calls[1][0]
    generator.repeat = False
    assert start(client, headers).status_code == 201


def test_daily_limit_and_concurrent_request_protection(client, generator, monkeypatch):
    headers = auth_headers(client)
    monkeypatch.setattr(get_settings(), "practice_ai_daily_questions", 10)
    assert start(client, headers).status_code == 201
    assert start(client, headers).status_code == 429
    assert len(generator.calls) == 1
    monkeypatch.setattr(get_settings(), "practice_ai_daily_questions", 250)

    async def lock():
        async with SessionLocal() as db:
            profile = await db.scalar(select(DoubtStudyProfile))
            profile.busy_until = datetime.now(UTC) + timedelta(minutes=1)
            await db.commit()

    asyncio.run(lock())
    assert start(client, headers).status_code == 429
    assert len(generator.calls) == 1


def test_failed_requests_are_also_rate_limited(client, generator):
    headers = auth_headers(client)
    generator.broken = True
    for _ in range(4):
        assert start(client, headers).status_code == 503
    calls = len(generator.calls)
    assert start(client, headers).status_code == 429
    assert len(generator.calls) == calls


def test_current_affairs_is_not_invented(client, generator):
    async def add_news():
        async with SessionLocal() as db:
            topic = await db.scalar(select(Topic).where(Topic.slug == "grammar"))
            db.add(
                Topic(subject_id=topic.subject_id, slug="current-affairs", name="Current affairs")
            )
            await db.commit()

    asyncio.run(add_news())
    headers = auth_headers(client)
    assert start(client, headers, topic_slug="current-affairs").status_code == 422
    assert generator.calls == []
    assert start(client, headers).status_code == 201
    assert "current-affairs" not in generator.calls[0][1]


def test_incomplete_valid_response_does_not_silently_shrink_a_50_question_set(client, generator):
    original = generator.generate_similar_questions

    async def partial(prompt, topics):
        output = await original(prompt, topics)
        return {"questions": output["questions"][:1]}

    generator.generate_similar_questions = partial
    headers = auth_headers(client)
    response = start(client, headers, 50)
    assert response.status_code == 503 and "full set" in response.json()["detail"]
    assert client.get("/api/v1/practice/attempts", headers=headers).json()["total"] == 0


def test_generated_private_questions_are_saved_to_the_owner(client, generator):
    headers = auth_headers(client)
    assert start(client, headers).status_code == 201

    async def inspect():
        async with SessionLocal() as db:
            attempt = await db.scalar(select(PracticeAttempt))
            owners = list(
                await db.scalars(
                    select(Question.owner_user_id).where(Question.owner_user_id.is_not(None))
                )
            )
            assert len(owners) == 10 and set(owners) == {attempt.user_id}

    asyncio.run(inspect())


def test_imitating_seed_questions_is_not_accepted_as_new_practice(client, generator):
    copied_prompt = "Select the correct sentence from the four given alternatives."

    async def update_seed():
        async with SessionLocal() as db:
            for q in await db.scalars(select(Question)):
                q.prompt = copied_prompt
            await db.commit()

    asyncio.run(update_seed())
    original = generator.generate_similar_questions

    async def copy_seed(prompt, topics):
        result = await original(prompt, topics)
        for item in result["questions"]:
            item["prompt"] = copied_prompt
        return result

    generator.generate_similar_questions = copy_seed
    headers = auth_headers(client)
    assert start(client, headers).status_code == 503
    assert client.get("/api/v1/practice/attempts", headers=headers).json()["total"] == 0


@pytest.mark.parametrize(
    "judgment",
    [
        {"usable": False, "answer_index": None},
        {"usable": True, "answer_index": 2},
        {"usable": True, "answer_index": True},
        {"usable": "true", "answer_index": 1},
    ],
)
def test_independent_review_rejects_bad_or_disagreed_answers(client, generator, judgment):
    async def reject(questions):
        return {"reviews": [{"number": i, **judgment} for i in range(1, len(questions) + 1)]}

    generator.review_similar_questions = reject
    headers = auth_headers(client)
    assert start(client, headers).status_code == 503
    assert client.get("/api/v1/practice/attempts", headers=headers).json()["total"] == 0


def test_quality_review_can_repair_a_partial_set_before_saving(client, generator):
    calls = 0
    original = generator.review_similar_questions

    async def reject_one(questions):
        nonlocal calls
        calls += 1
        result = await original(questions)
        if calls == 1:
            result["reviews"][0]["usable"] = False
        return result

    generator.review_similar_questions = reject_one
    headers = auth_headers(client)
    response = start(client, headers)
    assert response.status_code == 201 and len(response.json()["questions"]) == 10
    assert len(generator.calls) == 2


def test_missing_target_and_implicit_tasks_are_not_saved(client, generator):
    original = generator.generate_similar_questions

    async def incomplete(prompt, topics):
        result = await original(prompt, topics)
        for i, q in enumerate(result["questions"]):
            q["prompt"] = (
                "Choose the meaning of the underlined word in the sentence."
                if i % 2
                else "Affect and Effect in formal English usage."
            )
        return result

    generator.generate_similar_questions = incomplete
    headers = auth_headers(client)
    assert start(client, headers).status_code == 503
    assert client.get("/api/v1/practice/attempts", headers=headers).json()["total"] == 0


def test_final_missing_question_gets_a_bounded_extra_quality_repair(client, generator):
    calls = 0
    original = generator.review_similar_questions

    async def until_last(questions):
        nonlocal calls
        calls += 1
        result = await original(questions)
        if calls < 4:
            result["reviews"][0]["usable"] = False
        return result

    generator.review_similar_questions = until_last
    headers = auth_headers(client)
    response = start(client, headers)
    assert response.status_code == 201 and len(response.json()["questions"]) == 10
    assert calls == 4
