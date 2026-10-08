import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models.practice import Question, Subject, Topic
from app.models.study_plan import DailyStudyPlan
from app.services.rag import get_rag_service
from tests.test_similar_practice import PracticeGenerator


async def seed():
    async with SessionLocal() as db:
        for pos, (slug, name) in enumerate(
            [
                ("english", "English"),
                ("general-knowledge", "General Knowledge"),
                ("elementary-mathematics", "Mathematics"),
            ]
        ):
            subject = Subject(
                slug=slug, code=f"S{pos}", name=name, description="Test", position=pos
            )
            db.add(subject)
            await db.flush()
            for topic_slug in ["topic-one", "topic-two", "grammar"]:
                topic = Topic(subject_id=subject.id, slug=topic_slug, name=topic_slug)
                db.add(topic)
                await db.flush()
                for index in range(22):
                    db.add(
                        Question(
                            topic_id=topic.id,
                            prompt=f"Choose the correct agreement with neither, example {index}.",
                            options=["A", "B", "C", "D"],
                            correct_index=1,
                            explanation="The checked answer is B.",
                            provenance={
                                "kind": "pyq",
                                "paper_question_id": f"record-{index}",
                                "source_url": "https://upsc.gov.in/paper.pdf",
                                "year": 2025,
                                "number": index + 1,
                            },
                        )
                    )
        await db.commit()


@pytest.fixture(autouse=True)
def catalog(clean_database):
    asyncio.run(seed())
    fake = PracticeGenerator()
    app.dependency_overrides[get_rag_service] = lambda: fake
    with patch(
        "app.services.study_plan.now_utc", return_value=datetime(2026, 10, 8, 10, 0, tzinfo=UTC)
    ):
        yield fake
    app.dependency_overrides.pop(get_rag_service, None)


def auth(client, email="plan@example.com"):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Plan Student",
            "email": email,
            "password": "secure123",
        },
    )
    assert response.status_code == 201
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def setup(client, headers, minutes=120):
    response = client.put(
        "/api/v1/study-plan/preferences",
        headers=headers,
        json={
            "daily_minutes": minutes,
            "start_time": "19:00",
            "subject_slugs": ["english", "general-knowledge"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def act(client, headers, task, action):
    return client.patch(
        f"/api/v1/study-plan/tasks/{task['id']}", headers=headers, json={"action": action}
    )


def quiz(client, headers, task):
    return client.post(f"/api/v1/study-plan/tasks/{task['id']}/quiz", headers=headers)


def submit(client, headers, attempt, count, selected=1):
    return client.post(
        f"/api/v1/practice/attempts/{attempt['id']}/complete",
        headers=headers,
        json={
            "duration_seconds": 20,
            "answers": [
                {"question_id": q["id"], "selected_index": selected}
                for q in attempt["questions"][:count]
            ],
        },
    )


def test_setup_is_visible_persisted_and_idempotent(client):
    headers = auth(client)
    assert client.get("/api/v1/study-plan/today").status_code == 401
    first = client.get("/api/v1/study-plan/today", headers=headers).json()
    assert first["plan"] is None and first["preferences"]["configured"] is False
    assert first["preferences"]["subject_slugs"] == ["english", "general-knowledge"]
    assert client.post("/api/v1/study-plan/today", headers=headers).status_code == 409
    data = setup(client, headers)
    plan = data["plan"]
    assert plan["daily_minutes"] == 120 and len(plan["tasks"]) == 1
    assert plan["tasks"][0]["question_count"] == 50 and plan["version"] == 2
    assert sum(t["study_minutes"] + t["quiz_minutes"] for t in plan["tasks"]) == 120
    assert all(not t["completed"] and t["quiz_answered"] == 0 for t in plan["tasks"])
    again = client.post("/api/v1/study-plan/today", headers=headers).json()
    assert again["plan"] == plan and len(again["history"]) == 1


def test_settings_replace_only_an_untouched_plan(client):
    headers = auth(client)
    original = setup(client, headers)
    replaced = setup(client, headers, 60)
    assert replaced["plan"]["daily_minutes"] == 60
    assert original["plan"]["tasks"][0]["id"] != replaced["plan"]["tasks"][0]["id"]
    task = replaced["plan"]["tasks"][0]
    assert act(client, headers, task, "start").status_code == 200
    changed = setup(client, headers, 90)
    assert changed["settings_apply_tomorrow"] is True
    assert changed["preferences"]["daily_minutes"] == 90
    assert changed["plan"]["daily_minutes"] == 60
    assert changed["plan"]["tasks"][0]["id"] == task["id"]


def test_focus_timer_survives_refresh_pause_and_resume(client):
    headers = auth(client)
    tasks = setup(client, headers)["plan"]["tasks"]
    stamp = datetime(2026, 10, 8, 10, 0, tzinfo=UTC)
    with patch("app.services.study_plan.now_utc", return_value=stamp):
        started = act(client, headers, tasks[0], "start").json()["plan"]["tasks"][0]
        repeated = act(client, headers, tasks[0], "start").json()["plan"]["tasks"][0]
        assert repeated["study_started_at"] == started["study_started_at"]
    with patch("app.services.study_plan.now_utc", return_value=stamp + timedelta(seconds=90)):
        refreshed = client.get("/api/v1/study-plan/today", headers=headers).json()
        assert refreshed["plan"]["tasks"][0]["study_elapsed_seconds"] == 90
        switched = act(client, headers, tasks[0], "pause").json()["plan"]["tasks"]
        assert switched[0]["study_started_at"] is None
        assert switched[0]["study_elapsed_seconds"] == 90
        resumed = act(client, headers, tasks[0], "start").json()["plan"]["tasks"][0]
        assert resumed["study_started_at"] is not None


def test_ownership_topic_scope_and_no_answer_key_leaks(client):
    owner = auth(client)
    other = auth(client, "other@example.com")
    task = setup(client, owner)["plan"]["tasks"][0]
    for method, path, body in [
        ("get", f"/api/v1/study-plan/tasks/{task['id']}", None),
        ("patch", f"/api/v1/study-plan/tasks/{task['id']}", {"action": "complete"}),
        ("post", f"/api/v1/study-plan/tasks/{task['id']}/quiz", None),
    ]:
        assert (
            getattr(client, method)(
                path, headers=other, **({"json": body} if body else {})
            ).status_code
            == 404
        )
    assert quiz(client, owner, task).status_code == 409
    act(client, owner, task, "complete")
    forged = client.post(
        "/api/v1/practice/attempts",
        headers=owner,
        json={
            "subject_slug": "general-knowledge",
            "topic_slug": task["topic_slug"],
            "study_task_id": task["id"],
        },
    )
    assert forged.status_code == 422
    result = quiz(client, owner, task)
    assert result.status_code == 200
    attempt = result.json()
    assert len(attempt["questions"]) == task["question_count"]
    assert all(q["topic"] == "grammar" for q in attempt["questions"])
    assert attempt["question_mode"] == "daily"
    assert sum(q["provenance"]["kind"] == "pyq" for q in attempt["questions"]) == 20
    assert sum(q["provenance"]["kind"] == "generated" for q in attempt["questions"]) == 30
    assert all("correct_index" not in q and "explanation" not in q for q in attempt["questions"])
    assert quiz(client, owner, task).json()["id"] == attempt["id"]


def test_allocated_empty_and_unrelated_sets_never_complete_daily_target(client):
    headers = auth(client)
    task = setup(client, headers)["plan"]["tasks"][0]
    act(client, headers, task, "complete")
    unrelated = client.post(
        "/api/v1/practice/attempts",
        headers=headers,
        json={
            "subject_slug": task["subject_slug"],
            "topic_slug": task["topic_slug"],
            "question_count": task["question_count"],
            "allow_repeats": True,
        },
    ).json()
    submit(client, headers, unrelated, task["question_count"])
    blank = quiz(client, headers, task).json()
    submit(client, headers, blank, 0)
    today = client.get("/api/v1/study-plan/today", headers=headers).json()
    assert today["plan"]["completed_tasks"] == 0
    assert today["plan"]["tasks"][0]["quiz_answered"] == 0
    assert today["plan"]["tasks"][0]["completed"] is False


def test_daily_mixed_set_counts_all_questions_towards_the_limit(client, catalog, monkeypatch):
    headers = auth(client)
    task = setup(client, headers)["plan"]["tasks"][0]
    act(client, headers, task, "complete")
    # Thirty generated questions plus twenty PYQs still form a fifty-question set.
    monkeypatch.setattr(get_settings(), "practice_ai_daily_questions", 40)
    response = quiz(client, headers, task)
    assert response.status_code == 429
    assert not catalog.calls


def test_active_daily_quiz_hides_correctness_and_resumes_saved_answers(client):
    headers = auth(client)
    task = setup(client, headers)["plan"]["tasks"][0]
    act(client, headers, task, "complete")
    attempt = quiz(client, headers, task).json()
    saved = client.patch(
        f"/api/v1/practice/attempts/{attempt['id']}",
        headers=headers,
        json={
            "duration_seconds": 30,
            "current_position": 1,
            "answers": [{"question_id": attempt["questions"][0]["id"], "selected_index": 1}],
        },
    )
    assert saved.status_code == 200, saved.text
    today = client.get("/api/v1/study-plan/today", headers=headers).json()
    view = today["plan"]["tasks"][0]
    assert view["quiz_answered"] == 1 and view["quiz_correct"] == 0
    assert view["completed"] is False
    resumed = quiz(client, headers, task).json()
    assert resumed["id"] == attempt["id"] and len(resumed["answers"]) == 1
    assert resumed["elapsed_seconds"] == 30 and resumed["current_position"] == 1


def test_syllabus_sequence_is_not_replaced_by_a_random_weak_bank_topic(client):
    headers = auth(client)
    attempt = client.post(
        "/api/v1/practice/attempts",
        headers=headers,
        json={
            "subject_slug": "english",
            "topic_slug": "topic-one",
            "question_count": 5,
        },
    ).json()
    assert submit(client, headers, attempt, 5, selected=0).status_code == 200
    data = setup(client, headers)
    assert data["plan"]["tasks"][0]["curriculum_key"] == "agreement:1"
    assert data["plan"]["tasks"][0]["reason"] == "learn"
    other = auth(client, "independent@example.com")
    own_plan = setup(client, other)
    assert own_plan["plan"]["tasks"][0]["curriculum_key"] == "agreement:1"


def test_partial_quiz_can_finish_remaining_questions_without_losing_history(client):
    headers = auth(client)
    task = setup(client, headers)["plan"]["tasks"][0]
    act(client, headers, task, "complete")
    first = quiz(client, headers, task).json()
    assert submit(client, headers, first, 2).status_code == 200
    today = client.get("/api/v1/study-plan/today", headers=headers).json()
    assert today["plan"]["tasks"][0]["quiz_answered"] == 2
    assert today["plan"]["tasks"][0]["completed"] is False
    second = quiz(client, headers, task).json()
    assert second["id"] != first["id"]
    assert len(second["questions"]) == 50
    assert submit(client, headers, second, task["question_count"] - 2).status_code == 200
    today = client.get("/api/v1/study-plan/today", headers=headers).json()
    assert today["plan"]["completed_tasks"] == 1
    assert today["plan"]["tasks"][0]["quiz_correct"] == task["question_count"]
    assert quiz(client, headers, task).status_code == 409
    result = client.get(f"/api/v1/practice/attempts/{first['id']}/result", headers=headers)
    assert result.status_code == 200 and result.json()["answered_questions"] == 2


def test_ist_day_rollover_carries_work_without_marking_it_done(client):
    headers = auth(client)
    with patch(
        "app.services.study_plan.now_utc", return_value=datetime(2026, 10, 8, 18, 29, tzinfo=UTC)
    ):
        data = setup(client, headers)
        assert data["today"] == "2026-10-08"
        task = data["plan"]["tasks"][0]
        moved = act(client, headers, task, "defer").json()
        assert moved["plan"]["completed_tasks"] == 0
        assert moved["plan"]["tasks"][0]["deferred"] is True
        assert quiz(client, headers, task).status_code == 409
    with patch(
        "app.services.study_plan.now_utc", return_value=datetime(2026, 10, 8, 18, 31, tzinfo=UTC)
    ):
        data = client.post("/api/v1/study-plan/today", headers=headers).json()
        assert data["today"] == "2026-10-09" and len(data["history"]) == 2
        assert data["plan"]["tasks"][0]["topic_slug"] == task["topic_slug"]
        assert data["plan"]["tasks"][0]["curriculum_key"] == task["curriculum_key"]
        assert act(client, headers, task, "start").status_code == 409


@pytest.mark.parametrize(
    "change",
    [
        {"daily_minutes": 500},
        {"daily_minutes": True},
        {"start_time": "25:00"},
        {"subject_slugs": []},
        {"subject_slugs": ["english", "english"]},
        {"subject_slugs": ["unknown"]},
    ],
)
def test_invalid_preferences_are_rejected(client, change):
    headers = auth(client)
    payload = {"daily_minutes": 120, "start_time": "19:00", "subject_slugs": ["english"]}
    payload.update(change)
    assert (
        client.put("/api/v1/study-plan/preferences", headers=headers, json=payload).status_code
        == 422
    )


def test_checkin_is_owned_once_per_day_and_yes_studies_but_does_not_complete(client):
    headers = auth(client)
    other = auth(client, "other-checkin@example.com")
    task = setup(client, headers)["plan"]["tasks"][0]
    endpoint = "/api/v1/study-plan/checkin"
    body = {"task_id": task["id"], "answer": "not-yet"}
    assert client.post(endpoint, headers=other, json=body).status_code == 404
    result = client.post(endpoint, headers=headers, json=body).json()
    assert result["plan"]["checkin_seen"] is True
    assert result["plan"]["tasks"][0]["study_done"] is False
    assert result["plan"]["tasks"][0]["deferred"] is False
    body["answer"] = "yes"
    result = client.post(endpoint, headers=headers, json=body).json()
    assert result["plan"]["tasks"][0]["study_done"] is True
    assert result["plan"]["completed_tasks"] == 0
    assert result["roadmap_summary"]["completed_sessions"] == 0
    assert client.get("/api/v1/study-plan/today", headers=headers).json()["plan"]["checkin_seen"]


def test_quiz_failure_is_atomic_and_does_not_replace_a_saved_partial_quiz(client, catalog):
    headers = auth(client)
    task = setup(client, headers)["plan"]["tasks"][0]
    act(client, headers, task, "complete")
    first = quiz(client, headers, task).json()
    submit(client, headers, first, 2)
    catalog.broken = True
    assert quiz(client, headers, task).status_code == 503
    result = client.get("/api/v1/study-plan/today", headers=headers).json()
    assert result["plan"]["tasks"][0]["quiz_attempt_id"] == first["id"]
    assert result["plan"]["tasks"][0]["quiz_answered"] == 2
    assert len(client.get("/api/v1/practice/attempts", headers=headers).json()["items"]) == 1


def test_roadmap_does_not_duplicate_today_or_claim_it_completed(client):
    headers = auth(client)
    task = setup(client, headers)["plan"]["tasks"][0]
    result = client.get("/api/v1/study-plan/roadmap", headers=headers).json()
    assert result["days"][0]["curriculum_key"] == task["curriculum_key"]
    assert result["completed_sessions"] == 0
    assert sum(d["curriculum_key"] == task["curriculum_key"] for d in result["days"]) == 1
    assert result["coverage_deadline"] == "2027-02-11"
    assert result["feasible"]
    for bad_date in ["2026-10-08", "2028-01-01"]:
        response = client.put(
            "/api/v1/study-plan/preferences",
            headers=headers,
            json={
                "daily_minutes": 120,
                "start_time": "19:00",
                "subject_slugs": ["english"],
                "exam_date": bad_date,
            },
        )
        assert response.status_code == 422


def test_upgrade_keeps_saved_study_time_and_study_done(client):
    headers = auth(client)
    task = setup(client, headers)["plan"]["tasks"][0]
    act(client, headers, task, "complete")

    async def downgrade_for_upgrade_test():
        async with SessionLocal() as db:
            plan = await db.scalar(select(DailyStudyPlan))
            plan.version = 1
            await db.commit()

    asyncio.run(downgrade_for_upgrade_test())
    result = client.post("/api/v1/study-plan/today", headers=headers).json()
    assert result["plan"]["version"] == 2
    current = result["plan"]["tasks"][0]
    assert current["id"] == task["id"] and current["study_done"] is True
    assert current["question_count"] == 50 and current["quiz_answered"] == 0
    assert current["completed"] is False
