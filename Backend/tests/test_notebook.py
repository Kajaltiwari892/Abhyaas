import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.papers import PaperQuestion, PreviousPaper
from app.models.practice import Question, Subject, Topic


async def seed_catalog():
    async with SessionLocal() as db:
        db.add(
            Subject(
                id="english",
                slug="english",
                code="ENG",
                name="English",
                description="English practice",
            )
        )
        await db.flush()
        db.add(Topic(id="grammar", subject_id="english", slug="grammar", name="Grammar"))
        await db.flush()
        db.add(
            PreviousPaper(
                id="paper",
                subject_id="english",
                year=2024,
                cycle="I",
                title="CDS I 2024 English",
                exam_date=date(2024, 4, 21),
                official_question_count=5,
                academy_tracks=["OTA"],
                source_url="https://upsc.gov.in/paper.pdf",
                answer_key_url="https://upsc.gov.in/key.pdf",
            )
        )
        await db.flush()
        for number, qid in enumerate(
            ["paper-one", "paper-two", "pending", "pending-skip", "scan"], 1
        ):
            db.add(
                PaperQuestion(
                    id=qid,
                    paper_id="paper",
                    topic_id="grammar",
                    number=number,
                    prompt="Select the sentence with correct subject-verb agreement.",
                    options=["She goes home.", "She go home.", "She going home.", "She gone home."],
                    correct_index=0,
                    explanation="A singular subject takes 'goes'.",
                    source_label="Official UPSC answer key",
                    is_verified=qid not in {"pending", "pending-skip"},
                    transcription=None
                    if qid == "scan"
                    else dict(
                        prompt=f"Question {number}: Select the grammatically correct sentence.",
                        options=[
                            "She goes home.",
                            "She go home.",
                            "She going home.",
                            "She gone home.",
                        ],
                        sourcePageUrl="/papers/cds-i-2024/english/page-1.webp",
                    ),
                )
            )
        for qid in ["one", "two", "correct", "shared"]:
            db.add(
                Question(
                    id=qid,
                    topic_id="grammar",
                    prompt=f"{qid}: Select the grammatically correct sentence.",
                    options=["She goes home.", "She go home.", "She going home.", "She gone home."],
                    correct_index=0,
                    explanation="A singular subject takes 'goes'.",
                    provenance=dict(
                        kind="pyq",
                        paper_question_id="paper-one",
                        source_url="https://upsc.gov.in/paper.pdf",
                    )
                    if qid == "shared"
                    else None,
                )
            )
        await db.commit()


@pytest.fixture(autouse=True)
def catalog(clean_database):
    asyncio.run(seed_catalog())


def login(client: TestClient, email="revision@example.com"):
    response = client.post(
        "/api/v1/auth/register",
        json=dict(
            name="Revision Student",
            email=email,
            password="secure123",
        ),
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def completed_practice(client, headers, answers=None):
    response = client.post(
        "/api/v1/practice/attempts",
        headers=headers,
        json=dict(
            subject_slug="english",
            question_count=4,
            allow_repeats=True,
        ),
    )
    assert response.status_code == 201
    attempt = response.json()
    selections = {"one": 1, "shared": 1, "correct": 0} if answers is None else answers
    result = client.post(
        f"/api/v1/practice/attempts/{attempt['id']}/complete",
        headers=headers,
        json=dict(
            duration_seconds=30,
            answers=[
                dict(question_id=qid, selected_index=choice) for qid, choice in selections.items()
            ],
        ),
    )
    assert result.status_code == 200
    return result.json()


def test_notebook_backfills_only_completed_wrong_and_skipped_questions(client):
    headers = login(client)
    started = client.post(
        "/api/v1/practice/attempts",
        headers=headers,
        json=dict(subject_slug="english", question_count=4),
    )
    assert started.status_code == 201
    assert client.get("/api/v1/notebook", headers=headers).json()["total"] == 0
    result = completed_practice(client, headers)
    notebook = client.get("/api/v1/notebook", headers=headers).json()
    assert notebook["counts"] == dict(total=3, pending=3, resolved=0)
    assert notebook["revision_available"] == 3
    assert {q["question_key"] for q in notebook["items"]} == {
        "practice:one",
        "practice:two",
        "paper:paper-one",
    }
    assert len(client.get("/api/v1/notebook?reason=skipped", headers=headers).json()["items"]) == 1
    assert client.get("/api/v1/notebook?reason=skipped", headers=headers).json()["counts"] == dict(total=1, pending=1, resolved=0)
    assert client.get("/api/v1/notebook?reason=wrong", headers=headers).json()["counts"] == dict(total=2, pending=2, resolved=0)
    assert (
        client.get(
            f"/api/v1/practice/attempts/{result['attempt_id']}/result", headers=headers
        ).json()
        == result
    )


def test_papers_deduplicate_practice_pyqs_and_never_grade_missing_keys(client):
    headers = login(client)
    completed_practice(client, headers)
    attempt = client.post("/api/v1/papers/paper/attempts", headers=headers).json()
    response = client.post(
        f"/api/v1/paper-attempts/{attempt['id']}/complete",
        headers=headers,
        json=dict(
            duration_seconds=30,
            answers=[
                dict(question_id="paper-one", selected_index=1),
                dict(question_id="pending", selected_index=1),
            ],
        ),
    )
    assert response.status_code == 200
    notebook = client.get("/api/v1/notebook", headers=headers).json()
    assert notebook["counts"]["pending"] == 5
    entries = {q["question_key"]: q for q in notebook["items"]}
    assert "paper:pending" not in entries and "paper:pending-skip" not in entries
    assert entries["paper:paper-one"]["revision_ready"] is True
    assert entries["paper:scan"]["revision_ready"] is False
    assert notebook["revision_available"] == 4
    session = client.post(
        "/api/v1/notebook/sessions", headers=headers, json=dict(question_count=20)
    ).json()
    assert len(session["questions"]) == 4  # available checked, complete questions only
    assert "paper:scan" not in {q["question_key"] for q in session["questions"]}


def test_revision_is_saved_ungraded_until_finish_and_does_not_change_exam_scores(client):
    headers = login(client)
    original = completed_practice(client, headers)
    session = client.post(
        "/api/v1/notebook/sessions", headers=headers, json=dict(question_count=5)
    ).json()
    assert len(session["questions"]) == 3
    for question in session["questions"]:
        assert (
            not {"correct_index", "explanation", "selected_index", "mistake_selected_index", "is_correct"} & question.keys()
        )
    assert (
        client.get(f"/api/v1/notebook/sessions/{session['id']}/result", headers=headers).status_code
        == 409
    )
    payload = dict(
        current_position=1,
        answers=[
            dict(question_key=q["question_key"], selected_index=0) for q in session["questions"]
        ],
    )
    saved = client.patch(
        f"/api/v1/notebook/sessions/{session['id']}", headers=headers, json=payload
    )
    assert saved.status_code == 200
    assert client.get("/api/v1/notebook", headers=headers).json()["counts"]["pending"] == 3
    # A second start resumes rather than replacing the user's saved answers.
    resumed = client.post("/api/v1/notebook/sessions", headers=headers, json={}).json()
    assert resumed["id"] == session["id"] and resumed["current_position"] == 1
    assert len(resumed["answers"]) == 3
    result = client.post(
        f"/api/v1/notebook/sessions/{session['id']}/complete", headers=headers, json=payload
    ).json()
    assert result["correct_answers"] == 3 and result["skipped_questions"] == 0
    assert (
        client.post(
            f"/api/v1/notebook/sessions/{session['id']}/complete", headers=headers, json={}
        ).json()
        == result
    )
    assert (
        client.get(f"/api/v1/notebook/sessions/{session['id']}/result", headers=headers).json()
        == result
    )
    assert (
        client.patch(
            f"/api/v1/notebook/sessions/{session['id']}", headers=headers, json={}
        ).status_code
        == 409
    )
    notebook = client.get("/api/v1/notebook?state=resolved", headers=headers).json()
    assert notebook["counts"] == dict(total=3, pending=0, resolved=3)
    assert len(notebook["items"]) == 3
    assert all(q["selected_index"] == 0 for q in notebook["items"])
    earlier_choices = {q["question_key"]: q["mistake_selected_index"] for q in notebook["items"]}
    assert earlier_choices == {"practice:one": 1, "practice:two": None, "paper:paper-one": 1}
    assert notebook["recent_sessions"][0]["id"] == session["id"]
    assert notebook["recent_sessions"][0]["correct_answers"] == 3
    assert notebook["revision_available"] == 0
    assert (
        client.get(
            f"/api/v1/practice/attempts/{original['attempt_id']}/result", headers=headers
        ).json()
        == original
    )


def test_successful_later_practice_resolves_and_new_mistakes_reopen(client):
    headers = login(client)
    completed_practice(client, headers)
    completed_practice(client, headers, {"one": 0, "two": 0, "shared": 0, "correct": 0})
    assert client.get("/api/v1/notebook", headers=headers).json()["counts"] == dict(
        total=3, pending=0, resolved=3
    )
    completed_practice(client, headers)
    assert client.get("/api/v1/notebook", headers=headers).json()["counts"] == dict(
        total=3, pending=3, resolved=0
    )


def test_session_snapshot_survives_question_edits(client):
    headers = login(client)
    completed_practice(client, headers)
    session = client.post("/api/v1/notebook/sessions", headers=headers, json={}).json()

    async def edit_key():
        async with SessionLocal() as db:
            questions = (await db.scalars(select(Question))).all()
            for question in questions:
                question.correct_index = 2
            await db.commit()

    asyncio.run(edit_key())
    result = client.post(
        f"/api/v1/notebook/sessions/{session['id']}/complete",
        headers=headers,
        json=dict(
            answers=[
                dict(question_key=q["question_key"], selected_index=0) for q in session["questions"]
            ]
        ),
    ).json()
    assert result["correct_answers"] == 3


def test_ownership_validation_and_pagination(client):
    first = login(client)
    second = login(client, "other@example.com")
    completed_practice(client, first)
    assert client.get("/api/v1/notebook", headers=second).json()["total"] == 0
    page = client.get("/api/v1/notebook?limit=1", headers=first).json()
    assert len(page["items"]) == 1 and page["has_more"] and page["total"] == 3
    next_page = client.get("/api/v1/notebook?limit=1&offset=1", headers=first).json()
    assert page["items"][0]["question_key"] != next_page["items"][0]["question_key"]
    assert client.get("/api/v1/notebook?limit=51", headers=first).status_code == 422
    assert client.get("/api/v1/notebook?subject=missing", headers=first).status_code == 404
    session = client.post("/api/v1/notebook/sessions", headers=first, json={}).json()
    path = f"/api/v1/notebook/sessions/{session['id']}"
    for method, suffix in [("get", ""), ("patch", ""), ("post", "/complete"), ("get", "/result")]:
        response = getattr(client, method)(
            path + suffix, headers=second, **({"json": {}} if method != "get" else {})
        )
        assert response.status_code == 404
    choice = dict(question_key=session["questions"][0]["question_key"], selected_index=0)
    for payload in [
        dict(answers=[choice, choice]),
        dict(current_position=19),
        dict(answers=[dict(question_key="foreign", selected_index=0)]),
        dict(answers=[dict(**{**choice, "selected_index": 9})]),
    ]:
        assert client.patch(path, headers=first, json=payload).status_code == 422
    assert (
        client.post(
            "/api/v1/notebook/sessions", headers=first, json=dict(question_count=21)
        ).status_code
        == 422
    )


def test_empty_notebook_and_skipped_revision_remain_pending(client):
    headers = login(client)
    assert client.post("/api/v1/notebook/sessions", headers=headers, json={}).status_code == 409
    completed_practice(client, headers)
    session = client.post(
        "/api/v1/notebook/sessions", headers=headers, json=dict(reason="skipped")
    ).json()
    assert len(session["questions"]) == 1
    result = client.post(
        f"/api/v1/notebook/sessions/{session['id']}/complete", headers=headers, json={}
    ).json()
    assert result["skipped_questions"] == 1 and result["wrong_answers"] == 0
    assert client.get("/api/v1/notebook", headers=headers).json()["counts"]["pending"] == 3


def test_archived_questions_remain_reviewable_but_do_not_start_unreliable_sets(client):
    headers = login(client)
    completed_practice(client, headers)

    async def archive():
        async with SessionLocal() as db:
            for question in (await db.scalars(select(Question))).all():
                question.is_active = False
            await db.commit()

    asyncio.run(archive())
    notebook = client.get("/api/v1/notebook", headers=headers).json()
    assert notebook["counts"]["pending"] == 3
    assert notebook["revision_available"] == 0
    assert all(q["review_available"] and not q["revision_ready"] for q in notebook["items"])
    assert client.post("/api/v1/notebook/sessions", headers=headers, json={}).status_code == 409


def test_new_fault_after_successful_revision_reopens_the_question(client):
    headers = login(client)
    completed_practice(client, headers)
    session = client.post("/api/v1/notebook/sessions", headers=headers, json={}).json()
    result = client.post(
        f"/api/v1/notebook/sessions/{session['id']}/complete",
        headers=headers,
        json=dict(
            answers=[
                dict(question_key=q["question_key"], selected_index=0) for q in session["questions"]
            ]
        ),
    )
    assert result.status_code == 200
    completed_practice(client, headers, {"one": 1, "two": 0, "shared": 0, "correct": 0})
    notebook = client.get("/api/v1/notebook", headers=headers).json()
    assert notebook["counts"] == dict(total=3, pending=1, resolved=2)
    assert notebook["items"][0]["question_key"] == "practice:one"


def test_clearing_a_saved_choice_is_preserved_on_resume(client):
    headers = login(client)
    completed_practice(client, headers)
    session = client.post("/api/v1/notebook/sessions", headers=headers, json={}).json()
    path = f"/api/v1/notebook/sessions/{session['id']}"
    key = session["questions"][0]["question_key"]
    assert (
        client.patch(
            path, headers=headers, json=dict(answers=[dict(question_key=key, selected_index=0)])
        ).status_code
        == 200
    )
    assert (
        client.patch(
            path, headers=headers, json=dict(answers=[dict(question_key=key, selected_index=None)])
        ).status_code
        == 200
    )
    assert client.get(path, headers=headers).json()["answers"][key] is None


def test_notes_keep_latest_saved_mistake_when_later_practice_is_correct(client):
    headers = login(client)
    completed_practice(client, headers)
    completed_practice(client, headers, {"one": 2, "two": 0, "shared": 0, "correct": 0})
    completed_practice(client, headers, {"one": 0, "two": 0, "shared": 0, "correct": 0})
    entries = {
        q["question_key"]: q
        for q in client.get("/api/v1/notebook?state=resolved", headers=headers).json()["items"]
    }
    assert entries["practice:one"]["selected_index"] == 0
    assert entries["practice:one"]["mistake_selected_index"] == 2
    assert entries["practice:one"]["explanation"] == "A singular subject takes 'goes'."
    assert entries["practice:two"]["mistake_selected_index"] is None
    assert entries["practice:two"]["reason"] == "skipped"
