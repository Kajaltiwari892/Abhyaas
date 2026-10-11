import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import event, select
from sqlalchemy.dialects import postgresql

from app.db.session import SessionLocal, engine
from app.models.papers import PaperAnswer, PaperAttempt, PaperQuestion, PreviousPaper
from app.models.practice import PracticeAttempt, Question, Subject, Topic
from app.services.paper_answers import save_review


def seed_progress(client):
    registered = client.post("/api/v1/auth/register", json={
        "name": "Student", "email": "loading@example.com", "password": "secure123",
    }).json()
    other = client.post("/api/v1/auth/register", json={
        "name": "Other", "email": "other-loading@example.com", "password": "secure123",
    }).json()

    async def seed():
        async with SessionLocal() as db:
            subject = Subject(slug="english", code="ENG", name="English",
                              description="English", position=0)
            empty = Subject(slug="maths", code="MATH", name="Maths",
                            description="Maths", position=1)
            db.add_all([subject, empty])
            await db.flush()
            topic = Topic(subject_id=subject.id, slug="grammar", name="Grammar", position=0)
            db.add(topic)
            await db.flush()
            paper = PreviousPaper(
                subject_id=subject.id, year=2026, cycle="I", title="English paper",
                official_question_count=4, total_marks=100, academy_tracks=["OTA"],
                source_url="https://www.upsc.gov.in/paper.pdf",
                answer_key_url="https://www.upsc.gov.in/key.pdf",
            )
            db.add(paper)
            await db.flush()
            questions = [PaperQuestion(
                paper_id=paper.id, number=i, prompt=f"Question {i}", context=None,
                options=["A", "B", "C", "D"] if i != 4 else [], correct_index=1,
                explanation="Checked answer", source_label="UPSC",
                is_verified=i in {1, 4},
            ) for i in range(1, 5)]
            db.add_all(questions)
            await db.flush()
            save_review(questions[2], 2, "The question supports option C after checking.",
                        method="editorial", evidence={"checked": True})
            now = datetime.now(UTC)
            for i in range(15):
                attempt = PaperAttempt(
                    paper_id=paper.id, user_id=registered["user"]["id"], status="completed",
                    total_questions=4, correct_answers=0, scored_questions=0,
                    duration_seconds=120, completed_at=now - timedelta(minutes=i),
                )
                db.add(attempt)
                await db.flush()
                db.add_all([PaperAnswer(
                    attempt_id=attempt.id, question_id=q.id, selected_index=index, is_correct=False,
                ) for q, index in [(questions[0], 1), (questions[1], 1), (questions[2], 2)]])
            for i in range(13):
                db.add(PracticeAttempt(
                    user_id=registered["user"]["id"], subject_id=subject.id, topic_id=topic.id,
                    status="completed", total_questions=2, correct_answers=1, duration_seconds=60,
                    completed_at=now - timedelta(days=1, minutes=i),
                ))
            db.add(PracticeAttempt(
                user_id=other["user"]["id"], subject_id=subject.id, status="completed",
                total_questions=100, correct_answers=100, completed_at=now,
            ))
            db.add_all([Question(
                topic_id=topic.id, prompt="Public" if owner is None else "Private generated",
                options=["A", "B"], correct_index=0, explanation="Because A",
                owner_user_id=owner,
            ) for owner in [None, registered["user"]["id"]]])
            await db.commit()
    asyncio.run(seed())
    return {"Authorization": f"Bearer {registered['access_token']}"}


def record_sql():
    statements = []
    def record(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)
    event.listen(engine.sync_engine, "before_cursor_execute", record)
    return statements, record


def test_progress_keeps_all_time_totals_and_resolves_keys_once_per_paper(client, monkeypatch):
    headers = seed_progress(client)
    from app.api.v1 import progress
    resolver = progress.stored_answer
    resolved = []
    def tracked(question):
        resolved.append(question.id)
        return resolver(question)
    monkeypatch.setattr(progress, "stored_answer", tracked)
    statements, listener = record_sql()
    try:
        response = client.get("/api/v1/progress/dashboard", headers=headers)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", listener)
    assert response.status_code == 200
    data = response.json()
    assert data["completed_sets"] == 28
    assert data["questions_attempted"] == 86
    assert data["correct_answers"] == 43
    assert data["overall_accuracy"] == 76.8
    assert data["practice_seconds"] == 2580
    assert len(data["history"]) == 12
    assert len(resolved) == len(set(resolved)) == 4
    # Five dashboard reads plus one authentication read, independent of retakes.
    assert len(statements) == 6
    assert not any("paper_questions.asset_url" in sql for sql in statements)
    assert "public" not in response.headers.get("cache-control", "")
    assert client.get("/api/v1/progress/dashboard").status_code == 401


def test_progress_uses_changed_keys_and_invalidates_edited_reviewed_questions(client):
    headers = seed_progress(client)
    async def edit():
        async with SessionLocal() as db:
            questions = list(await db.scalars(select(PaperQuestion).order_by(PaperQuestion.number)))
            questions[0].correct_index = 2
            questions[2].prompt = "Changed question invalidates the old review"
            await db.commit()
    asyncio.run(edit())
    data = client.get("/api/v1/progress/dashboard", headers=headers).json()
    assert data["correct_answers"] == 13
    assert data["overall_accuracy"] == 31.7
    assert data["history"][0]["scored_questions"] == 1
    assert data["history"][0]["correct_answers"] == 0
    assert data["questions_attempted"] == 86


def test_public_subject_catalog_is_one_query_and_keeps_empty_subjects(client):
    seed_progress(client)
    statements, listener = record_sql()
    try:
        response = client.get("/api/v1/catalog/subjects")
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", listener)
    assert response.status_code == 200
    assert len(statements) == 1
    subjects = response.json()
    assert subjects[0]["question_count"] == 1  # Never includes a student's generated questions.
    assert subjects[1]["topics"] == []
    assert subjects[1]["question_count"] == 0
    assert response.headers["cache-control"] == "public, max-age=60, s-maxage=60"
    papers = client.get("/api/v1/papers")
    assert papers.status_code == 200
    assert papers.headers["cache-control"] == "public, max-age=60, s-maxage=60"


def test_refresh_lookup_uses_two_reads_and_keeps_the_user_lock():
    from app.auth.service import locked_refresh_session
    queries = []
    user, session = object(), object()
    async def scalar(query):
        queries.append(query)
        return user if len(queries) == 1 else session
    result = asyncio.run(locked_refresh_session(SimpleNamespace(scalar=scalar), "test-token"))
    assert result == (session, user)
    assert len(queries) == 2
    first = str(queries[0].compile(dialect=postgresql.dialect()))
    assert "FROM users" in first
    assert "SELECT refresh_sessions.user_id" in first
    assert first.endswith("FOR UPDATE")  # Same per-user serialization as logout/password reset.
    assert queries[1].get_execution_options()["populate_existing"] is True
