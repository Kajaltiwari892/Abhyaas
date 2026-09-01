import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.papers import PaperQuestion, PreviousPaper
from app.models.practice import Subject, Topic


async def seed_paper() -> None:
    async with SessionLocal() as db:
        subject = Subject(
            slug="english",
            code="ENG",
            name="English",
            description="English paper",
            position=0,
        )
        db.add(subject)
        await db.flush()
        topic = Topic(subject_id=subject.id, slug="grammar", name="Grammar", position=0)
        db.add(topic)
        await db.flush()
        paper = PreviousPaper(
            subject_id=subject.id,
            year=2024,
            cycle="I",
            title="CDS I 2024 - English",
            exam_date=date(2024, 4, 21),
            duration_seconds=7200,
            total_marks=100,
            official_question_count=120,
            negative_mark_fraction=1 / 3,
            academy_tracks=["IMA", "OTA Men"],
            source_url="https://www.upsc.gov.in/official-paper.pdf",
            is_published=True,
        )
        db.add(paper)
        await db.flush()
        db.add_all(
            [
                PaperQuestion(
                    paper_id=paper.id,
                    topic_id=topic.id,
                    number=number,
                    prompt=f"Paper question {number}",
                    options=["A", "B", "C", "D"],
                    correct_index=1,
                    explanation="B is correct.",
                    source_label="Official paper; verified explanation",
                    is_verified=True,
                )
                for number in range(1, 4)
            ]
        )
        await db.commit()


@pytest.fixture(autouse=True)
def paper_catalog(clean_database: None) -> None:
    asyncio.run(seed_paper())


def auth_headers(client: TestClient, email: str = "paper@example.com") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Paper User", "email": email, "password": "secure123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_paper_archive_review_and_mock_are_persisted(client: TestClient) -> None:
    headers = auth_headers(client)
    archive = client.get("/api/v1/papers?year=2024&cycle=I&subject=english")
    assert archive.status_code == 200
    paper = archive.json()[0]
    assert paper["available_question_count"] == 3
    assert paper["official_question_count"] == 120

    detail = client.get(f"/api/v1/papers/{paper['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["questions"][0]["correct_index"] == 1

    started = client.post(f"/api/v1/papers/{paper['id']}/attempts", headers=headers)
    assert started.status_code == 201
    attempt = started.json()
    first_question = attempt["questions"][0]
    assert "correct_index" not in first_question

    saved = client.put(
        f"/api/v1/paper-attempts/{attempt['id']}/answers/{first_question['id']}",
        headers=headers,
        json={"selected_index": 1, "marked_for_review": True},
    )
    assert saved.status_code == 200

    completed = client.post(
        f"/api/v1/paper-attempts/{attempt['id']}/complete",
        headers=headers,
        json={"duration_seconds": 120},
    )
    assert completed.status_code == 200
    assert completed.json()["correct_answers"] == 1
    assert completed.json()["unanswered_questions"] == 2
    assert completed.json()["score"] == 1

    dashboard = client.get("/api/v1/progress/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["completed_sets"] == 1
    assert dashboard.json()["history"][0]["topic"] == "Previous paper"


def test_paper_solutions_and_attempts_require_authentication(client: TestClient) -> None:
    paper_id = client.get("/api/v1/papers").json()[0]["id"]
    assert client.get(f"/api/v1/papers/{paper_id}").status_code == 401
    assert client.post(f"/api/v1/papers/{paper_id}/attempts").status_code == 401


def test_user_cannot_update_another_users_attempt(client: TestClient) -> None:
    owner_headers = auth_headers(client, "owner@example.com")
    other_headers = auth_headers(client, "other@example.com")
    paper_id = client.get("/api/v1/papers").json()[0]["id"]
    attempt = client.post(f"/api/v1/papers/{paper_id}/attempts", headers=owner_headers).json()
    question_id = attempt["questions"][0]["id"]
    response = client.put(
        f"/api/v1/paper-attempts/{attempt['id']}/answers/{question_id}",
        headers=other_headers,
        json={"selected_index": 1, "marked_for_review": False},
    )
    assert response.status_code == 404
