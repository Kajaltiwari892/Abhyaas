import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, update

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.practice import PracticeAttempt, Question
from app.models.rag import DoubtStudyProfile
from app.models.study_plan import DailyQuizPreparation
from app.services.lesson_bank_publication import publish, validate_bundle
from app.services.rag import RagUnavailableError, get_rag_service
from tests import test_study_plan as study_plan_tests
from tests.test_similar_practice import PracticeGenerator
from tests.test_study_plan import act, auth, setup


@pytest.fixture(autouse=True)
def catalog(clean_database):
    asyncio.run(study_plan_tests.seed())

    async def trim_fixture_bank():
        async with SessionLocal() as db:
            await db.execute(
                update(Question)
                .where(
                    Question.prompt.in_(
                        [
                            f"Choose the correct agreement with neither, example {i}."
                            for i in [20, 21]
                        ]
                    )
                )
                .values(is_active=False)
            )
            await db.commit()

    asyncio.run(trim_fixture_bank())
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


async def clear_backoff(task_id):
    async with SessionLocal() as db:
        draft = await db.get(DailyQuizPreparation, task_id)
        draft.next_retry_at = None
        await db.commit()


async def pending(task_id):
    async with SessionLocal() as db:
        draft = await db.get(DailyQuizPreparation, task_id)
        return list(draft.pending_questions), draft.failure_count


def finish(client, headers, url):
    for _ in range(16):
        response = client.post(url, headers=headers)
        assert response.status_code == 200, response.text
        if response.json()["status"] == "ready":
            return response.json()["attempt"]
    raise AssertionError("Quiz never became ready")


def test_steps_save_checked_batches_and_publish_exactly_one_full_quiz(client, catalog):
    headers, task, url = ready(client)
    response = client.post(url, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["prepared_count"] == 20
    assert response.json()["attempt"] is None and not catalog.calls
    for expected in [30, 40, 50]:
        generated = client.post(url, headers=headers)
        assert generated.status_code == 200, generated.text
        assert generated.json()["prepared_count"] == expected - 10
        assert generated.json()["phase"] == "checking"
        assert len(asyncio.run(pending(task["id"]))[0]) == 10
        assert asyncio.run(stored(task["id"])) == (expected - 30, None, 0)
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
    assert client.post(url, headers=headers).json()["prepared_count"] == 20
    assert client.post(url, headers=headers).json()["prepared_count"] == 30
    original = catalog.generate_similar_questions

    async def fail(*args, **kwargs):
        raise failure

    catalog.generate_similar_questions = fail
    response = client.post(url, headers=headers)
    assert response.status_code == 200 and response.json()["retry_after_ms"] > 0
    assert "saved" in response.json()["message"]
    assert asyncio.run(stored(task["id"])) == (10, None, 0)
    catalog.generate_similar_questions = original
    asyncio.run(clear_backoff(task["id"]))
    assert client.post(url, headers=headers).json()["prepared_count"] == 30
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
    assert client.post(url, headers=headers).json()["prepared_count"] == 20
    assert len(asyncio.run(pending(task["id"]))[0]) == 10


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
    assert client.post(url, headers=headers).status_code == 200
    response = client.post(url, headers=headers)
    assert response.status_code == 200 and response.json()["prepared_count"] == 20
    assert asyncio.run(stored(task["id"])) == (0, None, 0)
    assert not asyncio.run(pending(task["id"]))[0]


def test_duplicate_batches_are_rejected_without_losing_previous_questions(client, catalog):
    headers, task, url = ready(client)
    client.post(url, headers=headers)
    catalog.repeat = True
    assert client.post(url, headers=headers).json()["prepared_count"] == 20
    assert client.post(url, headers=headers).json()["prepared_count"] == 30
    assert client.post(url, headers=headers).json()["retry_after_ms"] > 0
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
    attempt = finish(client, headers, url)
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
    next_attempt = finish(client, headers, url)
    assert next_attempt["id"] != attempt["id"]
    assert len(next_attempt["questions"]) == 50


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
    attempt = finish(client, headers, url)
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


@pytest.mark.parametrize("failure", [RagUnavailableError("Provider offline"), TimeoutError()])
def test_review_outage_retries_saved_candidates_without_generating_again(client, catalog, failure):
    headers, task, url = ready(client)
    client.post(url, headers=headers)
    generated = client.post(url, headers=headers).json()
    assert generated["prepared_count"] == 20 and generated["phase"] == "checking"
    saved_candidates, _ = asyncio.run(pending(task["id"]))
    assert len(saved_candidates) == 10 and len(catalog.calls) == 1
    review = catalog.review_similar_questions
    review_calls = 0

    async def offline(*args, **kwargs):
        nonlocal review_calls
        review_calls += 1
        raise failure

    catalog.review_similar_questions = offline
    failed = client.post(url, headers=headers)
    assert failed.status_code == 200 and failed.json()["retry_after_ms"] > 0
    assert failed.json()["prepared_count"] == 20 and failed.json()["attempt"] is None
    assert asyncio.run(pending(task["id"])) == (saved_candidates, 1)
    assert asyncio.run(stored(task["id"])) == (0, None, 0)
    # Backoff is server enforced. A second browser cannot immediately hit the provider again.
    waiting = client.post(url, headers=headers)
    assert waiting.json()["phase"] == "waiting" and review_calls == 1
    assert len(catalog.calls) == 1
    catalog.review_similar_questions = review
    asyncio.run(clear_backoff(task["id"]))
    recovered = client.post(url, headers=headers).json()
    assert recovered["prepared_count"] == 30 and len(catalog.calls) == 1
    assert asyncio.run(pending(task["id"])) == ([], 0)


def test_permanent_provider_outage_stops_after_three_phases_not_forever(client, catalog):
    headers, task, url = ready(client)
    client.post(url, headers=headers)
    generation_calls = 0

    async def offline(*args, **kwargs):
        nonlocal generation_calls
        generation_calls += 1
        raise RagUnavailableError("Provider offline")

    catalog.generate_similar_questions = offline
    for failure in range(1, 4):
        asyncio.run(clear_backoff(task["id"]))
        response = client.post(url, headers=headers)
        assert response.status_code == (503 if failure == 3 else 200), response.text
        assert asyncio.run(pending(task["id"])) == ([], failure)
        assert asyncio.run(stored(task["id"])) == (0, None, 0)
    assert generation_calls == 3
    assert response.headers["retry-after"] == "30"
    assert "not your connection" in response.json()["detail"]
    assert "saved" in response.json()["detail"]


def test_realistic_zero_pyq_lesson_prepares_full_quiz_and_charges_creation_once(client, catalog):
    headers, task, url = ready(client)

    async def remove_pyqs():
        async with SessionLocal() as db:
            await db.execute(update(Question).values(is_active=False))
            await db.commit()

    asyncio.run(remove_pyqs())
    first = client.post(url, headers=headers)
    assert first.json()["prepared_count"] == 0
    reviews = 0
    review = catalog.review_similar_questions

    async def count_review(*args, **kwargs):
        nonlocal reviews
        reviews += 1
        return await review(*args, **kwargs)

    catalog.review_similar_questions = count_review
    attempt = finish(client, headers, url)
    assert len(attempt["questions"]) == 50 and len(catalog.calls) == 5 and reviews == 5
    assert len({q["prompt"] for q in attempt["questions"]}) == 50
    assert all(q["provenance"]["kind"] == "generated" for q in attempt["questions"])
    assert all(
        q["provenance"]["curriculum_key"] == task["curriculum_key"]
        and q["provenance"]["review_status"] == "independent_ai_checked"
        and q["provenance"]["answer_verified"] is False
        for q in attempt["questions"]
    )

    async def charged():
        async with SessionLocal() as db:
            return await db.scalar(select(DoubtStudyProfile.requests_in_window))

    assert asyncio.run(charged()) == 1


def agreement_bundle():
    path = Path(__file__).resolve().parents[1] / "data/lesson_banks/agreement_v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


async def publish_ready_bank(*, disable_pyqs=True):
    async with engine.begin() as connection:
        if disable_pyqs:
            await connection.execute(update(Question).values(is_active=False))
        return await connection.run_sync(lambda conn: publish(conn, agreement_bundle()))


def test_published_zero_pyq_lesson_opens_fifty_during_permanent_provider_outage(client, catalog):
    headers, task, url = ready(client)
    assert asyncio.run(publish_ready_bank()) == 50
    assert asyncio.run(publish_ready_bank(disable_pyqs=False)) == 0

    async def unavailable(*args, **kwargs):
        pytest.fail("Ready lesson bank must not call the unavailable AI service")

    catalog.generate_similar_questions = unavailable
    catalog.review_similar_questions = unavailable
    response = client.post(url, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready" and body["prepared_count"] == 50
    attempt = body["attempt"]
    assert len(attempt["questions"]) == len({q["id"] for q in attempt["questions"]}) == 50
    assert attempt["new_questions"] == 50 and attempt["repeated_questions"] == 0
    assert all(
        q["provenance"]["kind"] == "curated"
        and q["source_label"] == "Original CDS-style practice"
        and "source_url" not in q["provenance"]
        and "correct_index" not in q
        and "explanation" not in q
        for q in attempt["questions"]
    )
    resumed = client.post(url, headers=headers).json()["attempt"]
    assert resumed["id"] == attempt["id"]
    assert asyncio.run(stored(task["id"]))[2] == 1

    # Verify that the entire real bundle scores normally, without calling AI.
    async def keys():
        async with SessionLocal() as db:
            return dict((await db.execute(select(Question.id, Question.correct_index))).all())

    correct = asyncio.run(keys())
    submitted = client.post(
        f"/api/v1/practice/attempts/{attempt['id']}/complete",
        headers=headers,
        json={
            "duration_seconds": 1800,
            "answers": [
                {"question_id": q["id"], "selected_index": correct[q["id"]]}
                for q in attempt["questions"]
            ],
        },
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["correct_answers"] == 50
    assert len(submitted.json()["review"]) == 50
    assert all(item["explanation"] for item in submitted.json()["review"])


def test_published_pool_rescues_old_partial_draft_without_discarding_checked_questions(
    client, catalog
):
    headers, task, url = ready(client)
    client.post(url, headers=headers)
    client.post(url, headers=headers)  # Saved candidates, not yet checked.
    client.post(url, headers=headers)  # 10 checked originals + 20 PYQs.
    old = asyncio.run(stored(task["id"]))
    assert old[0] == 10
    asyncio.run(publish_ready_bank(disable_pyqs=False))

    async def unavailable(*args, **kwargs):
        pytest.fail("Existing partial draft should fill from the checked pool")

    catalog.generate_similar_questions = unavailable
    catalog.review_similar_questions = unavailable
    response = client.post(url, headers=headers)
    assert response.status_code == 200, response.text
    attempt = response.json()["attempt"]
    assert len(attempt["questions"]) == 50
    assert sum(q["provenance"]["kind"] == "generated" for q in attempt["questions"]) == 10
    assert sum(q["provenance"]["kind"] == "pyq" for q in attempt["questions"]) == 20


def test_seen_pool_stays_available_as_explicit_revision_and_unseen_comes_first(client, catalog):
    headers, _, url = ready(client)
    asyncio.run(publish_ready_bank())
    first = client.post(url, headers=headers).json()["attempt"]
    chosen = first["questions"][0]
    response = client.post(
        f"/api/v1/practice/attempts/{first['id']}/complete",
        headers=headers,
        json={
            "duration_seconds": 10,
            "answers": [{"question_id": chosen["id"], "selected_index": 0}],
        },
    )
    assert response.status_code == 200
    asyncio.run(reset_window())
    second = client.post(url, headers=headers).json()["attempt"]
    assert len(second["questions"]) == 50 and second["id"] != first["id"]
    assert second["repeated_questions"] == 1 and second["new_questions"] == 49
    assert second["questions"][-1]["id"] == chosen["id"]
    assert not catalog.calls


def test_ready_bank_refuses_mutation_of_published_questions_and_wrong_lesson():
    asyncio.run(publish_ready_bank())
    edited = agreement_bundle()
    edited["questions"][0]["correct_index"] = (edited["questions"][0]["correct_index"] + 1) % 4

    async def republish():
        async with engine.begin() as connection:
            await connection.run_sync(lambda conn: publish(conn, edited))

    with pytest.raises(ValueError, match="new bank version"):
        asyncio.run(republish())
    edited["subject_slug"] = "general-knowledge"
    with pytest.raises(ValueError, match="identity"):
        validate_bundle(edited)
