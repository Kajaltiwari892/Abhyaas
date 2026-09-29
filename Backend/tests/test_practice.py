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


def test_attempts_require_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/practice/attempts", json={"subject_slug": "english", "question_count": 3}
    )
    assert response.status_code == 401
