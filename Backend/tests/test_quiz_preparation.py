import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.practice import PracticeAttempt
from app.models.rag import DoubtStudyProfile
from app.models.study_plan import DailyQuizPreparation
from app.services.rag import RagUnavailableError, get_rag_service
from tests import test_study_plan as study_plan_tests
from tests.test_similar_practice import PracticeGenerator
from tests.test_study_plan import act, auth, setup


@pytest.fixture(autouse=True)
def catalog(clean_database):
    asyncio.run(study_plan_tests.seed())
    fake = PracticeGenerator()
    app.dependency_overrides[get_rag_service] = lambda: fake
    with patch(
        "app.services.study_plan.now_utc", return_value=datetime(2026, 10, 8, 10, tzinfo=UTC)
    ):
        yield fake
    app.dependency_overrides.pop(get_rag_service, None)


def ready(client):
    headers = auth(client)
    task = setup(client, headers)["plan"]["tasks"][0]
    assert act(client, headers, task, "complete").status_code == 200
    return headers, task, f"/api/v1/study-plan/tasks/{task['id']}/quiz/prepare"


async def stored(task_id):
    async with SessionLocal() as db:
        draft = await db.get(DailyQuizPreparation, task_id)
        attempts = await db.scalar(select(func.count()).select_from(PracticeAttempt))
        return len(draft.questions), draft.lease_token, attempts


async def reset_window():
    async with SessionLocal() as db:
        for profile in await db.scalars(select(DoubtStudyProfile)):
            profile.requests_in_window = 0
        await db.commit()


def test_steps_save_checked_batches_and_publish_exactly_one_full_quiz(client, catalog):
    headers, task, url = ready(client)
    response = client.post(url, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["prepared_count"] == 20
    assert response.json()["attempt"] is None and not catalog.calls
    for expected in [30, 40, 50]:
        response = client.post(url, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "preparing" and body["prepared_count"] == expected
        assert body["attempt"] is None  # Never leak a partial test or its answers.
        assert asyncio.run(stored(task["id"])) == (expected - 20, None, 0)
    result = client.post(url, headers=headers)
    assert result.status_code == 200, result.text
    attempt = result.json()["attempt"]
    assert len(attempt["questions"]) == 50 and attempt["duration_seconds"] == 3000
    assert len({q["id"] for q in attempt["questions"]}) == 50
    assert sum(q["provenance"]["kind"] == "pyq" for q in attempt["questions"]) == 20
    assert all("correct_index" not in q and "explanation" not in q for q in attempt["questions"])
    # A lost successful response / second tab must resume, not create another set.
    resumed = client.post(url, headers=headers).json()["attempt"]
    assert resumed["id"] == attempt["id"] and len(catalog.calls) == 3
    assert asyncio.run(stored(task["id"]))[2] == 1
    question = attempt["questions"][3]
    checkpoint = {
        "duration_seconds": 87,
        "current_position": 4,
        "answers": [
            {"question_id": question["id"], "selected_index": 1, "marked_for_review": True}
        ],
    }
    assert (
        client.patch(
            f"/api/v1/practice/attempts/{attempt['id']}", headers=headers, json=checkpoint
        ).status_code
        == 200
    )
    resumed = client.post(url, headers=headers).json()["attempt"]
    assert resumed["elapsed_seconds"] == 87 and resumed["current_position"] == 4
    assert resumed["answers"] == [
        {"question_id": question["id"], "selected_index": 1, "marked_for_review": True}
    ]


@pytest.mark.parametrize("failure", [RagUnavailableError("Provider offline"), TimeoutError()])
def test_failed_step_keeps_earlier_batches_and_releases_its_lease(client, catalog, failure):
    headers, task, url = ready(client)
    client.post(url, headers=headers)
    assert client.post(url, headers=headers).json()["prepared_count"] == 30
    original = catalog.generate_similar_questions

    async def fail(*args, **kwargs):
        raise failure

    catalog.generate_similar_questions = fail
    response = client.post(url, headers=headers)
    assert response.status_code == 503 and "saved" in response.json()["detail"]
    assert asyncio.run(stored(task["id"])) == (10, None, 0)
    catalog.generate_similar_questions = original
    asyncio.run(reset_window())
    assert client.post(url, headers=headers).json()["prepared_count"] == 40


def test_active_lease_and_rate_window_do_not_start_duplicate_provider_calls(client, catalog):
    headers, task, url = ready(client)
    client.post(url, headers=headers)

    async def lease(until):
        async with SessionLocal() as db:
            draft = await db.get(DailyQuizPreparation, task["id"])
            draft.lease_token, draft.lease_until = "existing-worker", until
            await db.commit()

    asyncio.run(lease(datetime.now(UTC) + timedelta(seconds=40)))
    response = client.post(url, headers=headers)
    assert response.json()["retry_after_ms"] == 2000 and not catalog.calls
    asyncio.run(lease(datetime.now(UTC) - timedelta(seconds=1)))
    assert client.post(url, headers=headers).json()["prepared_count"] == 30


def test_unreviewed_answers_never_enter_the_saved_draft(client, catalog):
    headers, task, url = ready(client)
    client.post(url, headers=headers)

    async def reject(questions, **kwargs):
        return {
            "reviews": [
                {"number": i, "usable": True, "answer_index": 0}
                for i in range(1, len(questions) + 1)
            ]
        }

    catalog.review_similar_questions = reject
    assert client.post(url, headers=headers).status_code == 503
    assert asyncio.run(stored(task["id"])) == (0, None, 0)


def test_duplicate_batches_are_rejected_without_losing_previous_questions(client, catalog):
    headers, task, url = ready(client)
    client.post(url, headers=headers)
    catalog.repeat = True
    assert client.post(url, headers=headers).json()["prepared_count"] == 30
    assert client.post(url, headers=headers).status_code == 503
    assert asyncio.run(stored(task["id"])) == (10, None, 0)


def test_expired_worker_cannot_overwrite_or_unlock_a_newer_batch(client, catalog):
    headers, task, url = ready(client)
    client.post(url, headers=headers)
    original = catalog.generate_similar_questions

    async def superseded(*args, **kwargs):
        async with SessionLocal() as db:
            draft = await db.get(DailyQuizPreparation, task["id"])
            draft.lease_token = "newer-worker"
            draft.lease_until = datetime.now(UTC) + timedelta(seconds=50)
            await db.commit()
        return await original(*args, **kwargs)

    catalog.generate_similar_questions = superseded
    assert client.post(url, headers=headers).json()["status"] == "preparing"
    assert asyncio.run(stored(task["id"])) == (0, "newer-worker", 0)


def test_saved_quiz_scores_normally_and_partial_submission_can_open_a_fresh_set(client):
    headers, task, url = ready(client)
    for _ in range(5):
        response = client.post(url, headers=headers)
    attempt = response.json()["attempt"]
    submitted = client.post(
        f"/api/v1/practice/attempts/{attempt['id']}/complete",
        headers=headers,
        json={
            "duration_seconds": 20,
            "answers": [{"question_id": attempt["questions"][0]["id"], "selected_index": 1}],
        },
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["correct_answers"] == 1 and len(submitted.json()["review"]) == 50
    asyncio.run(reset_window())
    for _ in range(5):
        response = client.post(url, headers=headers)
        assert response.status_code == 200, response.text
    assert response.json()["attempt"]["id"] != attempt["id"]
    assert len(response.json()["attempt"]["questions"]) == 50


def test_preparation_checks_ownership_study_state_and_full_quota(client, catalog, monkeypatch):
    headers, task, url = ready(client)
    other = auth(client, "another@example.com")
    assert client.post(url, headers=other).status_code == 404
    assert client.post(url).status_code == 401
    act(client, headers, task, "defer")
    assert client.post(url, headers=headers).status_code == 409
    act(client, headers, task, "restore")
    monkeypatch.setattr(get_settings(), "practice_ai_daily_questions", 40)
    assert client.post(url, headers=headers).status_code == 429
    assert not catalog.calls
    monkeypatch.setattr(get_settings(), "practice_ai_daily_questions", 60)
    assert client.post(url, headers=headers).status_code == 200
    # A 50-question pending draft cannot be bypassed through the similar route.
    response = client.post(
        "/api/v1/practice/attempts/similar",
        headers=headers,
        json={"subject_slug": "english", "topic_slug": "grammar", "question_count": 25},
    )
    assert response.status_code == 429


def test_repeated_checkpoint_skips_unchanged_answer_writes_and_extra_relation_queries(client):
    headers, _, url = ready(client)
    for _ in range(5):
        result = client.post(url, headers=headers).json()
    attempt = result["attempt"]
    payload = {
        "duration_seconds": 12,
        "current_position": 1,
        "answers": [{"question_id": attempt["questions"][0]["id"], "selected_index": 1}],
    }
    url = f"/api/v1/practice/attempts/{attempt['id']}"
    assert client.patch(url, headers=headers, json=payload).status_code == 200
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower().strip())

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        payload["duration_seconds"] = 17
        response = client.patch(url, headers=headers, json=payload)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)
    assert response.status_code == 200, response.text
    assert sum(sql.startswith("select") for sql in statements) == 4
    assert not any(sql.startswith("update practice_answers") for sql in statements)
