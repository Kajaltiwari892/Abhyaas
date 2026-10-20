"""Prepared lesson pools respect privacy, exact chapters and honest revision order."""

import asyncio
from types import SimpleNamespace

from app.db.session import SessionLocal
from app.models.auth import User
from app.models.practice import PracticeAnswer, PracticeAttempt, Question, Subject, Topic
from app.services.prepared_question_pool import choose_prepared_questions, top_up_prepared_bank

TASK = SimpleNamespace(
    curriculum_key="agreement:1", subject_slug="english", topic_slug="grammar"
)


async def seed(db):
    owner = User(id="owner", name="Owner", email="owner@example.com")
    other = User(id="other", name="Other", email="other@example.com")
    english = Subject(id="english", slug="english", name="English", code="EN", description="")
    gk = Subject(id="gk", slug="general-knowledge", name="GK", code="GK", description="")
    db.add_all([owner, other, english, gk])
    await db.flush()
    grammar = Topic(id="grammar", subject_id=english.id, slug="grammar", name="Grammar")
    errors = Topic(id="errors", subject_id=english.id, slug="error-spotting", name="Errors")
    vocab = Topic(id="vocab", subject_id=english.id, slug="vocabulary", name="Vocabulary")
    other_subject = Topic(id="other-topic", subject_id=gk.id, slug="grammar", name="Other")
    db.add_all([grammar, errors, vocab, other_subject])
    await db.flush()


def question(identity, *, kind="curated", owner=None, lesson="agreement", **changes):
    provenance = {
        "kind": kind,
        "curriculum_key": lesson,
        "review_status": "independent_ai_checked" if kind == "generated" else "content_checked",
        "answer_verified": False,
    }
    if kind == "pyq":
        provenance.update(paper_question_id=identity, source_url="https://upsc.gov.in/paper.pdf")
    values = dict(
        id=identity,
        topic_id="grammar",
        owner_user_id=owner,
        prompt=f"Choose the correct subject-verb agreement for example {identity}.",
        options=["is", "are", "be", "being"],
        correct_index=0,
        explanation="The singular subject takes a singular verb.",
        is_active=True,
        provenance=provenance,
    )
    values.update(changes)
    return Question(**values)


def test_pool_excludes_other_users_unchecked_wrong_lesson_and_public_generated_questions():
    async def scenario():
        async with SessionLocal() as db:
            await seed(db)
            accepted = [
                question("pyq", kind="pyq"),
                question("curated"),
                question(
                    "private-normalized", kind="generated", owner="owner", lesson="agreement:2"
                ),
                question(
                    "private-revision", kind="generated", owner="owner",
                    lesson="revision:agreement:2026-10-20",
                ),
                question("error-topic", topic_id="errors"),
            ]
            rejected = [
                question("other-private", kind="generated", owner="other"),
                question("private-untagged", kind="generated", owner="owner", lesson=None),
                question("private-wrong", kind="generated", owner="owner", lesson="tenses:1"),
                question("public-generated", kind="generated"),
                question("private-curated", owner="owner"),
                question("inactive", is_active=False),
                question("wrong-subject", topic_id="other-topic"),
                question("wrong-topic", topic_id="vocab"),
                question("invalid-key", correct_index=4),
                question("missing-explanation", explanation=" "),
                question("wrong-option-count", options=["is", "are", "be"]),
            ]
            unchecked = question("private-unchecked", kind="generated", owner="owner")
            unchecked.provenance = {**unchecked.provenance, "review_status": "pending"}
            rejected.append(unchecked)
            unapproved = question("curated-unapproved")
            unapproved.provenance = {**unapproved.provenance, "review_status": "pending"}
            rejected.append(unapproved)
            private_pyq = question("private-pyq", kind="pyq", owner="owner")
            rejected.append(private_pyq)
            db.add_all([*accepted, *rejected])
            await db.commit()
            selected = await choose_prepared_questions(db, "owner", TASK)
            assert {q.id for q in selected} == {q.id for q in accepted}
            assert selected[0].id == "pyq"
            assert all(q.owner_user_id in {None, "owner"} for q in selected)

    asyncio.run(scenario())


def test_repeatedly_rejected_reviews_stop_even_when_generation_keeps_succeeding(client):
    from datetime import UTC, datetime
    from unittest.mock import patch

    from app.main import app
    from app.models.study_plan import DailyQuizPreparation
    from app.services.rag import get_rag_service
    from tests.test_similar_practice import PracticeGenerator
    from tests.test_study_plan import act, auth, setup
    from tests.test_study_plan import seed as seed_plan

    asyncio.run(seed_plan())
    generator = PracticeGenerator()
    reviews = 0

    async def reject(questions, **kwargs):
        nonlocal reviews
        reviews += 1
        return {"reviews": [
            {"number": i, "usable": False, "answer_index": None}
            for i in range(1, len(questions) + 1)
        ]}

    async def reset_retry(task_id):
        async with SessionLocal() as db:
            draft = await db.get(DailyQuizPreparation, task_id)
            draft.next_retry_at = None
            await db.commit()

    generator.review_similar_questions = reject
    app.dependency_overrides[get_rag_service] = lambda: generator
    try:
        with patch(
            "app.services.study_plan.now_utc", return_value=datetime(2026, 10, 8, 10, tzinfo=UTC)
        ):
            headers = auth(client)
            task = setup(client, headers)["plan"]["tasks"][0]
            assert act(client, headers, task, "complete").status_code == 200
            url = f"/api/v1/study-plan/tasks/{task['id']}/quiz/prepare"
            first = client.post(url, headers=headers)
            prepared_count = first.json()["prepared_count"]
            assert prepared_count < 50
            for failure in range(1, 4):
                asyncio.run(reset_retry(task["id"]))
                generated = client.post(url, headers=headers)
                assert generated.status_code == 200
                assert generated.json()["prepared_count"] == prepared_count
                rejected = client.post(url, headers=headers)
                assert rejected.status_code == (503 if failure == 3 else 200), rejected.text
            assert reviews == 3 and len(generator.calls) == 3
            assert "Reliable questions" in rejected.json()["detail"]

            async def saved():
                async with SessionLocal() as db:
                    draft = await db.get(DailyQuizPreparation, task["id"])
                    return draft.questions, draft.pending_questions, draft.failure_count

            assert asyncio.run(saved()) == ([], [], 3)
    finally:
        app.dependency_overrides.pop(get_rag_service, None)


async def answered(db, user_id, questions):
    attempt = PracticeAttempt(
        user_id=user_id, subject_id="english", topic_id="grammar",
        total_questions=len(questions), status="completed",
    )
    db.add(attempt)
    await db.flush()
    db.add_all([
        PracticeAnswer(
            attempt_id=attempt.id, question_id=q.id, selected_index=0, is_correct=True
        )
        for q in questions
    ])


def test_pool_prioritizes_unseen_then_real_pyqs_and_counts_only_this_students_answers():
    async def scenario():
        async with SessionLocal() as db:
            await seed(db)
            new_pyq = question("99-pyq-new", kind="pyq")
            new_original = question("00-original-new")
            other_seen_original = question("01-other-student-saw-this")
            seen_pyq = question("02-pyq-seen", kind="pyq")
            seen_original = question("03-original-seen")
            db.add_all([new_pyq, new_original, other_seen_original, seen_pyq, seen_original])
            await db.flush()
            await answered(db, "owner", [seen_pyq, seen_original])
            await answered(db, "other", [other_seen_original])
            await db.commit()
            selected = await choose_prepared_questions(db, "owner", TASK)
            assert [q.id for q in selected] == [
                new_pyq.id, new_original.id, other_seen_original.id, seen_pyq.id, seen_original.id
            ]
            short = await choose_prepared_questions(db, "owner", TASK, limit=3)
            assert [q.id for q in short] == [new_pyq.id, new_original.id, other_seen_original.id]

    asyncio.run(scenario())


def test_pool_deduplicates_punctuation_and_honors_exclusions_and_unknown_lessons():
    async def scenario():
        async with SessionLocal() as db:
            await seed(db)
            first = question("a", prompt="Choose the correct agreement: A?")
            duplicate = question("b", prompt="Choose the correct agreement — A!")
            excluded = question("c")
            another = question("d")
            db.add_all([first, duplicate, excluded, another])
            await db.commit()
            selected = await choose_prepared_questions(
                db, "owner", TASK,
                exclude_ids=[excluded.id], exclude_prompts=["Choose the correct agreement A"],
            )
            assert [q.id for q in selected] == [another.id]
            assert await choose_prepared_questions(
                db, "owner", SimpleNamespace(curriculum_key="unknown"),
            ) == []
            assert await choose_prepared_questions(db, "owner", TASK, limit=0) == []

    asyncio.run(scenario())


def test_top_up_only_adds_checked_distinct_content_and_discards_surplus_pending_candidates():
    async def scenario():
        async with SessionLocal() as db:
            await seed(db)
            bank = [question(f"bank-{i:02}") for i in range(50)]
            db.add_all(bank)
            await db.commit()
            draft = SimpleNamespace(
                bank_ids=[bank[0].id],
                questions=[{"prompt": bank[1].prompt}],
                pending_questions=[{"prompt": f"Unchecked {i}"} for i in range(10)],
                failure_count=3, next_retry_at=None,
            )
            assert await top_up_prepared_bank(db, "owner", TASK, draft)
            assert len(draft.bank_ids) == 49
            assert len(set(draft.bank_ids)) == 49 and bank[1].id not in draft.bank_ids
            assert draft.pending_questions == [] and draft.failure_count == 0
            assert not await top_up_prepared_bank(db, "owner", TASK, draft)

    asyncio.run(scenario())
