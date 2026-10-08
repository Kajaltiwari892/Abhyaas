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
        db.add(
            PaperQuestion(
                paper_id=paper.id,
                topic_id=topic.id,
                number=4,
                prompt="Official scanned question 4",
                options=["Option (a)", "Option (b)", "Option (c)", "Option (d)"],
                correct_index=0,
                explanation="Answer verification pending.",
                source_label="Official paper scan",
                asset_url="/papers/example/page-2.webp",
                is_verified=False,
            )
        )
        await db.commit()


def test_checked_answer_scores_without_an_official_key_and_stays_hidden_during_mock(
    client: TestClient,
):
    from sqlalchemy import select

    from app.services.paper_answers import save_review

    async def review():
        async with SessionLocal() as db:
            q = await db.scalar(select(PaperQuestion).where(PaperQuestion.number == 4))
            save_review(
                q,
                2,
                "Option C is correct after independently checking all four choices.",
                method="editorial",
                evidence={"review": "checked"},
            )
            await db.commit()

    asyncio.run(review())
    headers = auth_headers(client)
    paper = client.get("/api/v1/papers").json()[0]
    assert paper["scorable_question_count"] == 4
    assert paper["reviewed_question_count"] == 1
    detail = client.get(f"/api/v1/papers/{paper['id']}", headers=headers).json()
    q = detail["questions"][3]
    assert q["is_verified"] is False and q["is_scorable"] is True
    assert q["correct_index"] == 2 and q["answer_basis"] == "reviewed"
    attempt = client.post(f"/api/v1/papers/{paper['id']}/attempts", headers=headers).json()
    assert "correct_index" not in attempt["questions"][3]
    saved = client.put(
        f"/api/v1/paper-attempts/{attempt['id']}/answers/{q['id']}",
        json={"selected_index": 2},
        headers=headers,
    ).json()
    assert saved["is_correct"] is None and saved["correct_index"] is None
    result = client.post(
        f"/api/v1/paper-attempts/{attempt['id']}/complete",
        json={"duration_seconds": 50},
        headers=headers,
    ).json()
    assert result["correct_answers"] == 1 and result["scored_questions"] == 4
    assert result["score"] == 0.83 and result["score_basis"] == "practice"
    assert result["review"][3]["answer_basis"] == "reviewed"


def test_old_results_and_dashboard_use_new_keys_not_stale_correctness(client: TestClient):
    from app.services.paper_answers import save_review

    headers = auth_headers(client)
    paper = client.get("/api/v1/papers").json()[0]
    attempt = client.post(f"/api/v1/papers/{paper['id']}/attempts", headers=headers).json()
    qid = attempt["questions"][3]["id"]
    result = client.post(
        f"/api/v1/paper-attempts/{attempt['id']}/complete",
        json={"duration_seconds": 75, "answers": [{"question_id": qid, "selected_index": 2}]},
        headers=headers,
    ).json()
    assert result["scored_questions"] == 3 and result["correct_answers"] == 0

    async def review(index):
        async with SessionLocal() as db:
            q = await db.get(PaperQuestion, qid)
            save_review(
                q,
                index,
                "The checked answer uses the exact current wording and options.",
                method="editorial",
                evidence={"review": "updated"},
            )
            await db.commit()

    asyncio.run(review(2))
    result = client.get(f"/api/v1/paper-attempts/{attempt['id']}/result", headers=headers).json()
    assert result["scored_questions"] == 4 and result["correct_answers"] == 1
    assert result["review"][3]["selected_index"] == 2 and result["review"][3]["is_correct"] is True
    dashboard = client.get("/api/v1/progress/dashboard", headers=headers).json()
    assert dashboard["correct_answers"] == 1 and dashboard["history"][0]["scored_questions"] == 4
    notebook = client.get("/api/v1/notebook", headers=headers).json()
    assert all(q["question_key"] != f"paper:{qid}" for q in notebook["items"])
    asyncio.run(review(1))
    result = client.get(f"/api/v1/paper-attempts/{attempt['id']}/result", headers=headers).json()
    assert result["correct_answers"] == 0 and result["incorrect_answers"] == 1
    notebook = client.get("/api/v1/notebook", headers=headers).json()
    assert (
        next(q for q in notebook["items"] if q["question_key"] == f"paper:{qid}")["reason"]
        == "wrong"
    )


def test_a_question_edit_invalidates_its_practice_answer(client: TestClient):
    from sqlalchemy import select

    from app.services.paper_answers import save_review

    async def change():
        async with SessionLocal() as db:
            q = await db.scalar(select(PaperQuestion).where(PaperQuestion.number == 4))
            save_review(
                q,
                2,
                "The original wording supports this checked answer.",
                method="editorial",
                evidence={"review": "checked"},
            )
            q.options = ["A", "Changed B", "C", "D"]
            await db.commit()

    asyncio.run(change())
    headers = auth_headers(client)
    paper = client.get("/api/v1/papers").json()[0]
    assert paper["scorable_question_count"] == 3
    detail = client.get(f"/api/v1/papers/{paper['id']}", headers=headers).json()
    assert detail["questions"][3]["correct_index"] is None


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


def test_pdf_only_archive_lists_without_fake_mock_or_date(client: TestClient) -> None:
    async def add_archive():
        from sqlalchemy import select

        async with SessionLocal() as db:
            subject = (await db.execute(select(Subject))).scalars().first()
            db.add(
                PreviousPaper(
                    id="pdf-only",
                    subject_id=subject.id,
                    year=2016,
                    cycle="II",
                    title="CDS II 2016 - English",
                    exam_date=None,
                    official_question_count=120,
                    academy_tracks=["OTA"],
                    source_url="https://upsc.gov.in/old-paper.pdf",
                )
            )
            await db.commit()

    asyncio.run(add_archive())
    response = client.get("/api/v1/papers?year=2016&cycle=II&subject=english")
    assert response.status_code == 200
    paper = response.json()[0]
    assert paper["exam_date"] is None
    assert paper["available_question_count"] == 0
    assert paper["verified_question_count"] == 0
    assert paper["solutions_available"] is False
    assert (
        client.post("/api/v1/papers/pdf-only/attempts", headers=auth_headers(client)).status_code
        == 409
    )


def test_paper_archive_review_and_mock_are_persisted(client: TestClient) -> None:
    headers = auth_headers(client)
    archive = client.get("/api/v1/papers?year=2024&cycle=I&subject=english")
    assert archive.status_code == 200
    paper = archive.json()[0]
    assert paper["available_question_count"] == 4
    assert paper["verified_question_count"] == 3
    assert paper["official_question_count"] == 120

    detail = client.get(f"/api/v1/papers/{paper['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["questions"][0]["correct_index"] == 1
    assert len(detail.json()["questions"]) == 4
    assert detail.json()["questions"][-1]["correct_index"] is None
    assert detail.json()["questions"][-1]["is_verified"] is False

    started = client.post(f"/api/v1/papers/{paper['id']}/attempts", headers=headers)
    assert started.status_code == 201
    attempt = started.json()
    first_question = attempt["questions"][0]
    assert len(attempt["questions"]) == 4
    assert "correct_index" not in first_question
    assert attempt["resumed"] is False
    assert attempt["elapsed_seconds"] == 0
    assert attempt["answers"] == []
    pending_result = client.get(f"/api/v1/paper-attempts/{attempt['id']}/result", headers=headers)
    assert pending_result.status_code == 409

    saved = client.put(
        f"/api/v1/paper-attempts/{attempt['id']}/answers/{first_question['id']}",
        headers=headers,
        json={"selected_index": 1, "marked_for_review": True, "elapsed_seconds": 45},
    )
    assert saved.status_code == 200
    assert saved.json()["is_correct"] is None
    assert saved.json()["correct_index"] is None

    resumed = client.post(f"/api/v1/papers/{paper['id']}/attempts", headers=headers)
    assert resumed.status_code == 201
    assert resumed.json()["id"] == attempt["id"]
    assert resumed.json()["resumed"] is True
    assert resumed.json()["elapsed_seconds"] == 45
    assert resumed.json()["answers"][0]["selected_index"] == 1
    assert resumed.json()["answers"][0]["marked_for_review"] is True
    assert resumed.json()["answers"][0]["is_correct"] is None
    assert resumed.json()["answers"][0]["correct_index"] is None

    unverified_question = attempt["questions"][-1]
    unverified_saved = client.put(
        f"/api/v1/paper-attempts/{attempt['id']}/answers/{unverified_question['id']}",
        headers=headers,
        json={"selected_index": 2, "marked_for_review": False},
    )
    assert unverified_saved.status_code == 200

    completed = client.post(
        f"/api/v1/paper-attempts/{attempt['id']}/complete",
        headers=headers,
        json={
            "duration_seconds": 120,
            "answers": [
                {
                    "question_id": attempt["questions"][1]["id"],
                    "selected_index": 0,
                    "marked_for_review": False,
                }
            ],
        },
    )
    assert completed.status_code == 200
    assert completed.json()["correct_answers"] == 1
    assert completed.json()["unanswered_questions"] == 1
    assert completed.json()["answered_questions"] == 3
    assert completed.json()["scored_questions"] == 3
    assert completed.json()["unscored_questions"] == 1
    assert completed.json()["incorrect_answers"] == 1
    assert completed.json()["score"] == 0.56
    assert completed.json()["max_score"] == 2.5
    assert completed.json()["accuracy"] == 33.3
    assert completed.json()["review"][-1]["correct_index"] is None
    assert completed.json()["review"][-1]["is_correct"] is None

    recovered = client.get(f"/api/v1/paper-attempts/{attempt['id']}/result", headers=headers)
    assert recovered.status_code == 200
    assert recovered.json() == completed.json()

    repeated_completion = client.post(
        f"/api/v1/paper-attempts/{attempt['id']}/complete",
        headers=headers,
        json={"duration_seconds": 999, "answers": []},
    )
    assert repeated_completion.status_code == 200
    assert repeated_completion.json() == completed.json()

    dashboard = client.get("/api/v1/progress/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["completed_sets"] == 1
    assert dashboard.json()["history"][0]["topic"] == "Previous paper"
    assert dashboard.json()["questions_attempted"] == 4
    assert dashboard.json()["history"][0]["scored_questions"] == 3

    restarted = client.post(f"/api/v1/papers/{paper['id']}/attempts", headers=headers)
    assert restarted.status_code == 201
    assert restarted.json()["id"] != attempt["id"]
    assert restarted.json()["resumed"] is False


def test_paper_solutions_and_attempts_require_authentication(client: TestClient) -> None:
    paper_id = client.get("/api/v1/papers").json()[0]["id"]
    assert client.get(f"/api/v1/papers/{paper_id}").status_code == 401
    assert client.post(f"/api/v1/papers/{paper_id}/attempts").status_code == 401
    assert client.get("/api/v1/paper-attempts/missing/result").status_code == 401


def test_ai_explanation_reports_missing_configuration(client: TestClient) -> None:
    headers = auth_headers(client, "ai-config@example.com")
    paper = client.get("/api/v1/papers").json()[0]
    detail = client.get(f"/api/v1/papers/{paper['id']}", headers=headers).json()
    scanned_question = detail["questions"][-1]

    response = client.post(
        f"/api/v1/papers/{paper['id']}/questions/{scanned_question['id']}/ai-explanation",
        headers=headers,
    )

    assert response.status_code == 503
    assert "Gemini API key" in response.json()["detail"]


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
