import copy

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.auth import User
from app.models.papers import PaperAnswer, PaperAttempt, PaperQuestion, PreviousPaper
from app.models.practice import (
    AttemptQuestion,
    PracticeAnswer,
    PracticeAttempt,
    Question,
    Subject,
    Topic,
)
from app.models.rag import DoubtConversation, DoubtMessage
from scripts.transfer_user_history import MODELS, export_history, transfer_history, validate_bundle


@pytest.fixture
async def transfer_data():
    from datetime import UTC, date, datetime

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = async_sessionmaker(engine, expire_on_commit=False)
    async with session() as db:
        source = User(
            id="source",
            name="Student",
            email="student@example.test",
            password_hash="must-not-export",
            google_sub="must-not-export",
            is_active=True,
            is_verified=True,
        )
        db.add(source)
        db.add(Subject(id="s", slug="english", code="ENG", name="English", description=""))
        await db.flush()
        db.add(Topic(id="t", subject_id="s", slug="grammar", name="Grammar"))
        db.add(
            PreviousPaper(
                id="p",
                subject_id="s",
                year=2025,
                cycle="II",
                title="Paper",
                exam_date=date(2025, 9, 1),
                official_question_count=1,
                academy_tracks=["OTA"],
                source_url="https://example.test/paper.pdf",
            )
        )
        await db.flush()
        db.add(
            Question(
                id="q",
                topic_id="t",
                prompt="Question",
                options=["A", "B"],
                correct_index=1,
                explanation="Explanation",
            )
        )
        db.add(
            PaperQuestion(
                id="pq",
                paper_id="p",
                number=1,
                prompt="Paper question",
                options=["A", "B"],
                correct_index=0,
                explanation="Explanation",
                source_label="Official",
            )
        )
        db.add(
            PracticeAttempt(
                id="pa",
                user_id="source",
                subject_id="s",
                topic_id="t",
                status="completed",
                total_questions=1,
                correct_answers=1,
                duration_seconds=23,
                completed_at=datetime.now(UTC),
            )
        )
        db.add(
            PaperAttempt(
                id="pp",
                user_id="source",
                paper_id="p",
                total_questions=1,
                status="in_progress",
                duration_seconds=180,
            )
        )
        db.add(DoubtConversation(id="c", user_id="source", title="Private study chat"))
        await db.flush()
        db.add(AttemptQuestion(id="aq", attempt_id="pa", question_id="q", position=0))
        db.add(
            PracticeAnswer(
                id="a", attempt_id="pa", question_id="q", selected_index=1, is_correct=True
            )
        )
        db.add(
            PaperAnswer(
                id="pap", attempt_id="pp", question_id="pq", selected_index=0, is_correct=True
            )
        )
        db.add(
            DoubtMessage(
                id="m",
                conversation_id="c",
                role="assistant",
                content="Private answer",
                citations=[{"url": "https://example.test/source"}],
                pyq_result={"questions": [{"id": "pq"}]},
            )
        )
        await db.commit()
        bundle = await export_history(db, "student@example.test")
        for model in reversed(MODELS):
            await db.execute(delete(model))
        source.email = "old-local@example.test"
        db.add(
            User(
                id="live",
                name="Student",
                email="student@example.test",
                is_active=True,
                is_verified=True,
                password_hash="live-password-unchanged",
            )
        )
        db.add(User(id="other", name="Other", email="other@example.test", is_verified=True))
        await db.commit()
    yield bundle, session
    await engine.dispose()


@pytest.mark.asyncio
async def test_check_is_read_only_and_export_excludes_credentials(transfer_data):
    bundle, session = transfer_data
    assert "password" not in str(bundle) and "must-not-export" not in str(bundle)
    async with session() as db, db.begin():
        report = await transfer_history(db, bundle)
        assert report["would_insert"]["doubt_messages"] == 1
        assert (
            await db.execute(select(func.count()).select_from(PracticeAttempt))
        ).scalar_one() == 0


@pytest.mark.asyncio
async def test_transfer_verifies_all_fields_and_is_idempotent(transfer_data):
    bundle, session = transfer_data
    async with session() as db, db.begin():
        db.add(DoubtConversation(id="existing", user_id="live", title="Keep this"))
    async with session() as db, db.begin():
        result = await transfer_history(db, bundle, apply=True)
        assert result["existing_live"]["doubt_conversations"] == 1
        assert sum(result["inserted"].values()) == 7
    async with session() as db, db.begin():
        # Once imported, live edits must survive any accidental retry.
        attempt = await db.get(PaperAttempt, "pp")
        attempt.duration_seconds = 200
        message = await db.get(DoubtMessage, "m")
        assert message.citations == bundle["tables"]["doubt_messages"][0]["citations"]
        assert (await db.get(PracticeAttempt, "pa")).duration_seconds == 23
        assert (await db.get(User, "live")).password_hash == "live-password-unchanged"
    async with session() as db, db.begin():
        second = await transfer_history(db, bundle, apply=True)
        assert sum(second["inserted"].values()) == 0
        assert (await db.get(PaperAttempt, "pp")).duration_seconds == 200
        assert (await db.get(DoubtConversation, "existing")).title == "Keep this"


@pytest.mark.asyncio
async def test_foreign_account_id_collision_aborts_everything(transfer_data):
    bundle, session = transfer_data
    async with session() as db, db.begin():
        db.add(DoubtConversation(id="c", user_id="other", title="Someone else's chat"))
    with pytest.raises(ValueError, match="another account"):
        async with session() as db, db.begin():
            await transfer_history(db, bundle, apply=True)
    async with session() as db:
        assert await db.get(PracticeAttempt, "pa") is None
        assert (await db.get(DoubtConversation, "c")).user_id == "other"


@pytest.mark.asyncio
async def test_catalog_mismatch_aborts_without_writes(transfer_data):
    bundle, session = transfer_data
    async with session() as db, db.begin():
        (await db.get(Question, "q")).options = ["Changed", "Options"]
    with pytest.raises(ValueError, match="catalog"):
        async with session() as db, db.begin():
            await transfer_history(db, bundle, apply=True)
    async with session() as db:
        assert await db.get(PracticeAttempt, "pa") is None


@pytest.mark.asyncio
async def test_unverified_target_rejected(transfer_data):
    bundle, session = transfer_data
    async with session() as db, db.begin():
        (await db.get(User, "live")).is_verified = False
    with pytest.raises(ValueError, match="Verified matching"):
        async with session() as db, db.begin():
            await transfer_history(db, bundle, apply=True)


@pytest.mark.asyncio
async def test_bundle_rejects_extra_tables_or_cross_account_rows(transfer_data):
    bundle, _ = transfer_data
    changed = copy.deepcopy(bundle)
    changed["tables"]["users"] = []
    with pytest.raises(ValueError, match="tables"):
        validate_bundle(changed)
    changed = copy.deepcopy(bundle)
    changed["tables"]["practice_attempts"][0]["user_id"] = "other"
    with pytest.raises(ValueError, match="Mixed source"):
        validate_bundle(changed)
    changed = copy.deepcopy(bundle)
    changed["tables"]["doubt_messages"][0]["conversation_id"] = "not-owned"
    with pytest.raises(ValueError, match="outside source"):
        validate_bundle(changed)
