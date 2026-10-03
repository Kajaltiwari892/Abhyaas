import asyncio

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.practice import Question, Subject, Topic


async def seed_catalog() -> None:
    async with SessionLocal() as db:
        subject = Subject(
            slug="english",
            code="ENG",
            name="English",
            description="English practice",
            position=0,
        )
        db.add(subject)
        await db.flush()
        topic = Topic(subject_id=subject.id, slug="grammar", name="Grammar", position=0)
        db.add(topic)
        await db.flush()
        db.add_all(
            [
                Question(
                    topic_id=topic.id,
                    prompt=f"Question {index}",
                    options=["A", "B", "C", "D"],
                    correct_index=1,
                    explanation="B is correct.",
                    source_label="Original practice",
                )
                for index in range(3)
            ]
        )
        await db.commit()


@pytest.fixture(autouse=True)
def practice_catalog(clean_database: None) -> None:
    asyncio.run(seed_catalog())


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Practice User", "email": "practice@example.com", "password": "secure123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_catalog_and_practice_flow_are_persisted(client: TestClient) -> None:
    headers = auth_headers(client)
    catalog = client.get("/api/v1/catalog/subjects")
    assert catalog.status_code == 200
    assert catalog.json()[0]["topics"][0]["name"] == "Grammar"

    started = client.post(
        "/api/v1/practice/attempts",
        headers=headers,
        json={"subject_slug": "english", "question_count": 3},
    )
    assert started.status_code == 201
    attempt = started.json()
    assert len(attempt["questions"]) == 3
    question_id = attempt["questions"][0]["id"]

    saved = client.put(
        f"/api/v1/practice/attempts/{attempt['id']}/answers/{question_id}",
        headers=headers,
        json={"selected_index": 1, "marked_for_review": False},
    )
    assert saved.status_code == 200

    completed = client.post(
        f"/api/v1/practice/attempts/{attempt['id']}/complete",
        headers=headers,
        json={"duration_seconds": 90},
    )
    assert completed.status_code == 200
    assert completed.json()["answered_questions"] == 1
    assert completed.json()["correct_answers"] == 1

    dashboard = client.get("/api/v1/progress/dashboard", headers=headers)
    assert dashboard.status_code == 200
    data = dashboard.json()
    assert data["completed_sets"] == 1
    assert data["questions_attempted"] == 3
    assert data["practice_seconds"] == 90

    # A preparation preference must not reset scores, saved answers or elapsed time.
    unfinished = client.post(
        "/api/v1/practice/attempts", headers=headers,
        json={"subject_slug": "english", "question_count": 3, "allow_repeats": True},
    )
    assert unfinished.status_code == 201
    unfinished_id = unfinished.json()["id"]
    before = client.get(f"/api/v1/practice/attempts/{unfinished_id}", headers=headers)
    assert before.status_code == 200
    for target in ["ota", "ima", None]:
        saved_target = client.patch(
            "/api/v1/users/me/preferences", headers=headers, json={"target_academy": target}
        )
        assert saved_target.status_code == 200
        assert client.get("/api/v1/progress/dashboard", headers=headers).json() == data
        assert client.get(
            f"/api/v1/practice/attempts/{unfinished_id}", headers=headers
        ).json() == before.json()


def test_attempts_require_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/practice/attempts", json={"subject_slug": "english", "question_count": 3}
    )
    assert response.status_code == 401


def test_catalog_filters_counts_and_pagination(client: TestClient) -> None:
    async def another_subject():
        async with SessionLocal() as db:
            subject = Subject(
                slug="maths", code="MATH", name="Maths", description="Numbers", position=1
            )
            db.add(subject)
            await db.flush()
            topic = Topic(subject_id=subject.id, slug="algebra", name="Algebra", position=0)
            empty = Topic(subject_id=subject.id, slug="geometry", name="Geometry", position=1)
            db.add_all([topic, empty])
            await db.flush()
            db.add(
                Question(
                    topic_id=topic.id,
                    prompt="Solve x + 1 = 2",
                    options=["0", "1"],
                    correct_index=1,
                    explanation="Subtract 1",
                )
            )
            db.add(
                Question(
                    topic_id=topic.id,
                    prompt="Hidden",
                    options=["0", "1"],
                    correct_index=1,
                    explanation="Hidden",
                    is_active=False,
                )
            )
            await db.commit()

    asyncio.run(another_subject())
    catalog = client.get("/api/v1/catalog/subjects").json()
    assert [s["question_count"] for s in catalog] == [3, 1]
    assert catalog[1]["topics"][1]["question_count"] == 0
    first = client.get(
        "/api/v1/catalog/questions?subject_slug=english&topic_slug=grammar&limit=2"
    ).json()
    second = client.get("/api/v1/catalog/questions?subject_slug=english&offset=2&limit=2").json()
    assert first["total"] == 3 and first["has_more"] is True
    assert len(second["questions"]) == 1 and second["has_more"] is False
    assert not {q["id"] for q in first["questions"]} & {q["id"] for q in second["questions"]}
    assert all("correct_index" not in q for q in first["questions"])
    maths = client.get("/api/v1/catalog/questions?subject_slug=maths").json()
    assert maths["total"] == 1 and maths["questions"][0]["topic"] == "Algebra"
    assert (
        client.get("/api/v1/catalog/questions?subject_slug=maths&topic_slug=geometry").json()[
            "total"
        ]
        == 0
    )
    assert (
        client.get("/api/v1/catalog/questions?subject_slug=maths&topic_slug=grammar").status_code
        == 404
    )
    assert client.get("/api/v1/catalog/questions?subject_slug=unknown").status_code == 404
    assert (
        client.get("/api/v1/catalog/questions?subject_slug=english&limit=1000").status_code == 422
    )


def test_checkpoint_resume_atomic_submit_and_result_history(client: TestClient) -> None:
    headers = auth_headers(client)
    attempt = client.post(
        "/api/v1/practice/attempts",
        headers=headers,
        json={"subject_slug": "english", "topic_slug": "grammar", "question_count": 3},
    ).json()
    base = f"/api/v1/practice/attempts/{attempt['id']}"
    questions = attempt["questions"]
    assert attempt["subject_slug"] == "english" and attempt["topic_slug"] == "grammar"
    assert client.get(f"{base}/result", headers=headers).status_code == 409
    answers = [{"question_id": questions[0]["id"], "selected_index": 0, "marked_for_review": True}]
    assert (
        client.patch(
            base, headers=headers, json={"duration_seconds": 75, "answers": answers}
        ).status_code
        == 200
    )
    resumed = client.get(base, headers=headers).json()
    assert resumed["answers"] == answers and resumed["elapsed_seconds"] == 75
    assert all("correct_index" not in q for q in resumed["questions"])
    assert "is_correct" not in resumed["answers"][0]
    # Submitting includes the changed current answer and a second unsaved answer.
    answers[0]["selected_index"] = 1
    answers.append({"question_id": questions[1]["id"], "selected_index": 0})
    response = client.post(
        f"{base}/complete", headers=headers, json={"duration_seconds": 95, "answers": answers}
    )
    assert response.status_code == 200
    result = response.json()
    assert result["correct_answers"] == 1 and result["answered_questions"] == 2
    assert result["score"] == 0.67
    assert result["review"][2]["selected_index"] is None
    assert result["review"][0]["options"] == ["A", "B", "C", "D"]
    assert result["review"][0]["prompt"] == questions[0]["prompt"]
    assert client.get(f"{base}/result", headers=headers).json() == result
    # A retried submit cannot alter the already completed result.
    answers[0]["selected_index"] = 0
    assert (
        client.post(
            f"{base}/complete", headers=headers, json={"duration_seconds": 150, "answers": answers}
        ).json()
        == result
    )
    assert (
        client.patch(
            base, headers=headers, json={"duration_seconds": 100, "answers": answers}
        ).status_code
        == 409
    )
    history = client.get("/api/v1/practice/attempts", headers=headers).json()
    assert history["total"] == 1 and history["items"][0]["status"] == "completed"
    assert history["items"][0]["correct_answers"] == 1


def test_attempt_validation_and_ownership(client: TestClient) -> None:
    headers = auth_headers(client)
    other = client.post(
        "/api/v1/auth/register",
        json={"name": "Other", "email": "other@example.com", "password": "secure123"},
    ).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    attempt = client.post(
        "/api/v1/practice/attempts", headers=headers, json={"subject_slug": "english"}
    ).json()
    base = f"/api/v1/practice/attempts/{attempt['id']}"
    assert client.get("/api/v1/practice/attempts", headers=other_headers).json()["items"] == []
    assert client.get(base, headers=other_headers).status_code == 404
    assert client.get(f"{base}/result", headers=other_headers).status_code == 404
    assert (
        client.patch(base, headers=other_headers, json={"duration_seconds": 0}).status_code == 404
    )
    assert (
        client.post(
            f"{base}/complete", headers=other_headers, json={"duration_seconds": 0}
        ).status_code
        == 404
    )
    valid = {"question_id": attempt["questions"][0]["id"], "selected_index": 1}
    for invalid in [
        {"question_id": "not-in-attempt", "selected_index": 1},
        {"question_id": attempt["questions"][1]["id"], "selected_index": 9},
        valid,
    ]:
        assert (
            client.post(
                f"{base}/complete",
                headers=headers,
                json={"duration_seconds": 20, "answers": [valid, invalid]},
            ).status_code
            == 422
        )
        assert client.get(base, headers=headers).json()["answers"] == []
    assert client.get("/api/v1/practice/attempts?limit=10000", headers=headers).status_code == 422
    assert client.get("/api/v1/practice/attempts").status_code == 401


def test_history_has_unfinished_sets_and_is_paginated(client: TestClient) -> None:
    headers = auth_headers(client)
    for _ in range(3):
        assert (
            client.post(
                "/api/v1/practice/attempts",
                headers=headers,
                json={"subject_slug": "english", "allow_repeats": True},
            ).status_code
            == 201
        )
    first = client.get("/api/v1/practice/attempts?limit=2", headers=headers).json()
    second = client.get("/api/v1/practice/attempts?limit=2&offset=2", headers=headers).json()
    assert first["total"] == 3 and first["has_more"] is True
    assert len(second["items"]) == 1 and not second["has_more"]
    assert all(item["status"] == "in_progress" for item in first["items"])
    assert first["items"][0]["id"] != second["items"][0]["id"]


def test_fresh_sets_exhaust_pool_without_repeating_and_revision_is_explicit(client: TestClient):
    headers = auth_headers(client)
    endpoint = "/api/v1/practice/attempts"
    availability = "/api/v1/practice/availability?subject_slug=english&topic_slug=grammar"
    assert client.get(availability, headers=headers).json() == {"total": 3, "seen": 0, "unseen": 3}
    first = client.post(
        endpoint, headers=headers, json={"subject_slug": "english", "question_count": 2}
    ).json()
    second = client.post(
        endpoint, headers=headers, json={"subject_slug": "english", "question_count": 2}
    ).json()
    assert len(first["questions"]) == 2 and len(second["questions"]) == 1
    assert first["duration_seconds"] == 120 and second["duration_seconds"] == 60
    assert not {q["id"] for q in first["questions"]} & {q["id"] for q in second["questions"]}
    assert client.get(availability, headers=headers).json() == {"total": 3, "seen": 3, "unseen": 0}
    assert (
        client.post(endpoint, headers=headers, json={"subject_slug": "english"}).status_code == 409
    )
    revision = client.post(
        endpoint, headers=headers, json={"subject_slug": "english", "allow_repeats": True}
    ).json()
    assert len(revision["questions"]) == 3 and revision["repeated_questions"] == 3
    assert client.get(availability).status_code == 401


def test_saved_set_keeps_all_questions_elapsed_time_and_position(client: TestClient):
    headers = auth_headers(client)
    attempt = client.post(
        "/api/v1/practice/attempts", headers=headers, json={"subject_slug": "english"}
    ).json()
    base = f"/api/v1/practice/attempts/{attempt['id']}"
    answer = {"question_id": attempt["questions"][1]["id"], "selected_index": 2}
    assert (
        client.patch(
            base,
            headers=headers,
            json={"duration_seconds": 80, "current_position": 2, "answers": [answer]},
        ).status_code
        == 200
    )
    # Reading history does not start or reset a timer, and unanswered items remain.
    for _ in range(2):
        saved = client.get(base, headers=headers).json()
        assert saved["questions"] == attempt["questions"] and len(saved["answers"]) == 1
        assert saved["elapsed_seconds"] == 80 and saved["duration_seconds"] == 180
        assert saved["current_position"] == 2
    assert client.patch(base, headers=headers, json={"duration_seconds": 40}).status_code == 200
    assert client.get(base, headers=headers).json()["elapsed_seconds"] == 80
    assert (
        client.patch(
            base, headers=headers, json={"duration_seconds": 85, "current_position": 3}
        ).status_code
        == 422
    )
    assert client.patch(base, headers=headers, json={"duration_seconds": 500}).status_code == 200
    assert client.get(base, headers=headers).json()["elapsed_seconds"] == 180


def test_large_set_honors_requested_size_and_topic_filter(client: TestClient):
    async def add_questions():
        from sqlalchemy import select

        async with SessionLocal() as db:
            topic = (await db.execute(select(Topic).where(Topic.slug == "grammar"))).scalar_one()
            db.add_all(
                [
                    Question(
                        topic_id=topic.id,
                        prompt=f"Exam question {i}",
                        options=["a", "b", "c", "d"],
                        correct_index=0,
                        explanation="Explanation",
                    )
                    for i in range(105)
                ]
            )
            await db.commit()

    asyncio.run(add_questions())
    headers = auth_headers(client)
    attempt = client.post(
        "/api/v1/practice/attempts",
        headers=headers,
        json={"subject_slug": "english", "topic_slug": "grammar", "question_count": 100},
    ).json()
    assert len(attempt["questions"]) == 100 and attempt["duration_seconds"] == 6000
    assert len({q["id"] for q in attempt["questions"]}) == 100
    assert all(q["topic"] == "Grammar" for q in attempt["questions"])
    answers = [{"question_id": q["id"], "selected_index": 0} for q in attempt["questions"]]
    result = client.post(
        f"/api/v1/practice/attempts/{attempt['id']}/complete",
        headers=headers,
        json={"duration_seconds": 5000, "answers": answers},
    )
    assert result.status_code == 200 and result.json()["answered_questions"] == 100
    assert len(result.json()["review"]) == 100
