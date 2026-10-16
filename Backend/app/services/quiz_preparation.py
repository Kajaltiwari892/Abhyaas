"""Prepare a full quiz in durable, bounded steps, not one long HTTP request.

Each accepted batch is committed before replying. Repeating a request, losing
the response or moving to another server instance never creates a second quiz.
No in-process background tasks are used: serverless instances can stop safely.
"""

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.auth import User
from app.models.practice import (
    AttemptQuestion,
    PracticeAnswer,
    PracticeAttempt,
    Question,
    Topic,
    new_id,
)
from app.models.rag import DoubtStudyProfile
from app.models.study_plan import DailyQuizPreparation, DailyStudyPlan, DailyStudyTask
from app.schemas.study_plan import DailyQuizPreparationResponse
from app.services.daily_quiz import matches_lesson, ready_task
from app.services.practice_sets import PracticeQuestion
from app.services.rag import RagService, RagUnavailableError
from app.services.study_curriculum import find_unit
from app.services.study_memory import locked_profile

BATCH_SIZE = 10
STEP_SECONDS = 35
LEASE_SECONDS = 50


def fingerprint(prompt: str) -> str:
    return re.sub(r"\W+", "", prompt).casefold()


def progress(draft: DailyQuizPreparation, *, waiting: bool = False):
    return DailyQuizPreparationResponse(
        status="preparing",
        prepared_count=len(draft.bank_ids) + len(draft.questions),
        retry_after_ms=2000 if waiting else 0,
    )


async def choose_bank(db: AsyncSession, user_id: str, task) -> list[Question]:
    topics = [task.topic_slug]
    if task.subject_slug == "english" and task.topic_slug in {"grammar", "error-spotting"}:
        topics = ["grammar", "error-spotting"]
    rows = await db.scalars(
        select(Question)
        .join(Topic)
        .where(
            Topic.subject.has(slug=task.subject_slug),
            Topic.slug.in_(topics),
            Question.owner_user_id.is_(None),
            Question.is_active.is_(True),
            ~Question.id.in_(
                select(PracticeAnswer.question_id)
                .join(PracticeAttempt)
                .where(PracticeAttempt.user_id == user_id)
            ),
        )
        .order_by(Question.id)
    )
    unit, bank, seen = find_unit(task.curriculum_key), [], set()
    for question in rows:
        source = question.provenance or {}
        key = fingerprint(question.prompt)
        if (
            source.get("kind") == "pyq"
            and source.get("paper_question_id")
            and source.get("source_url")
            and 0 <= question.correct_index < len(question.options)
            and (not unit or matches_lesson(question, unit))
            and key not in seen
        ):
            bank.append(question)
            seen.add(key)
            if len(bank) == 20:
                break
    return bank


async def reviewed_batch(rag: RagService, task, count: int, avoid: list[str]) -> list[dict]:
    focus = task.topic_name + ". Focus only on: " + "; ".join(task.focus_points or [])
    prompt = f"""Create exactly {count} ORIGINAL CDS/OTA exam-level multiple-choice questions.
Subject: {task.subject_name}. Lesson: {focus}.
Mostly moderate/challenging UPSC CDS depth; not beginner trivia. Cover different concepts.
English: nuanced error spotting, grammar or contextual word use matching this lesson.
GK: use comparisons and statement-based reasoning. Maths: multi-step school-syllabus problems.
Each question needs a FULL explicit instruction, all necessary text and four plausible options.
No unseen passages, underlined/highlighted words, images, isolated word pairs or fragments.
Solve first; exactly one option is correct. Include a short, accurate explanation.
No current-affairs guesses. These are original practice, never claim they are actual PYQs.
Return JSON: {{"questions":[{{"prompt":"...","options":["...","...","...","..."],
"correct_index":0,"explanation":"...","topic_slug":"{task.topic_slug}"}}]}}.
Do not repeat these questions: {json.dumps(avoid[-100:], ensure_ascii=False)}
"""
    raw = await rag.generate_similar_questions(prompt, [task.topic_slug])
    candidates, seen = [], {fingerprint(text) for text in avoid}
    for item in raw.get("questions", [])[:count] if isinstance(raw.get("questions"), list) else []:
        try:
            question = PracticeQuestion.model_validate(item).model_dump()
        except ValidationError:
            continue
        key = fingerprint(question["prompt"])
        if (
            question["topic_slug"] != task.topic_slug
            or key in seen
            or re.search(r"underlined|highlighted", question["prompt"], re.I)
            or not re.search(
                r"\?|\b(?:choose|select|which|what|identify|spot|determine|find|"
                r"compute|calculate|arrange|match|complete)\b",
                question["prompt"],
                re.I,
            )
        ):
            continue
        seen.add(key)
        candidates.append(question)
    if not candidates:
        return []
    review = await rag.review_similar_questions(candidates, focus_detail=focus)
    judgments = {}
    for judgment in review.get("reviews", []) if isinstance(review.get("reviews"), list) else []:
        if isinstance(judgment, dict) and type(judgment.get("number")) is int:
            number = judgment["number"]
            judgments[number] = None if number in judgments else judgment
    return [
        q
        for i, q in enumerate(candidates, 1)
        if (j := judgments.get(i))
        and j.get("usable") is True
        and type(j.get("answer_index")) is int
        and j["answer_index"] == q["correct_index"]
    ]


async def finish_draft(db: AsyncSession, user: User, task, draft: DailyQuizPreparation):
    from app.api.v1.practice import get_attempt

    # Every id is assigned up front: one bulk flush, not 30–50 DB round trips.
    topic = await db.scalar(
        select(Topic).where(
            Topic.slug == task.topic_slug, Topic.subject.has(slug=task.subject_slug)
        )
    )
    if topic is None:
        raise HTTPException(404, "Topic not found")
    attempt = PracticeAttempt(
        id=new_id(),
        user_id=user.id,
        subject_id=topic.subject_id,
        topic_id=topic.id,
        total_questions=50,
        time_limit_seconds=50 * (72 if task.subject_slug == "elementary-mathematics" else 60),
        negative_mark_fraction=1 / 3,
        question_mode="daily",
    )
    db.add(attempt)
    ids = list(draft.bank_ids)
    for item in draft.questions:
        question = Question(
            id=new_id(),
            topic_id=topic.id,
            owner_user_id=user.id,
            prompt=item["prompt"],
            options=item["options"],
            correct_index=item["correct_index"],
            explanation=item["explanation"],
            difficulty="cds",
            source_label="AI-created CDS-style practice",
            provenance={"kind": "generated", "answer_verified": False},
        )
        db.add(question)
        ids.append(question.id)
    if len(ids) != 50:
        raise HTTPException(409, "Your quiz is still being prepared.")
    await db.flush()
    db.add_all(
        [
            AttemptQuestion(attempt_id=attempt.id, question_id=qid, position=i)
            for i, qid in enumerate(ids, 1)
        ]
    )
    if task.quiz_attempt and task.quiz_attempt.status == "completed":
        task.previous_quiz_answered += len(task.quiz_attempt.answers)
        task.previous_quiz_correct += sum(a.is_correct for a in task.quiz_attempt.answers)
    task.quiz_attempt = attempt
    draft.attempt_id = attempt.id
    draft.lease_token = draft.lease_until = None
    await db.commit()
    return DailyQuizPreparationResponse(
        status="ready", prepared_count=50, attempt=await get_attempt(attempt.id, user, db)
    )


async def prepare_step(db: AsyncSession, user: User, task_id: str, rag: RagService):
    from app.api.v1.practice import get_attempt

    user_id = user.id
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    task = await ready_task(db, user.id, task_id)
    if task.quiz_attempt and task.quiz_attempt.status == "in_progress":
        return DailyQuizPreparationResponse(
            status="ready",
            prepared_count=task.quiz_attempt.total_questions,
            attempt=await get_attempt(task.quiz_attempt.id, user, db),
        )
    now = datetime.now(UTC)
    draft = await db.get(DailyQuizPreparation, task_id, populate_existing=True)
    if draft is None or draft.attempt_id:
        profile = await locked_profile(db, user.id)
        if profile.busy_until and profile.busy_until.replace(tzinfo=UTC) > now:
            raise HTTPException(429, "Please wait for your current set or answer to finish.")
        if not profile.request_window_started or now - profile.request_window_started.replace(
            tzinfo=UTC
        ) >= timedelta(minutes=1):
            profile.request_window_started, profile.requests_in_window = now, 0
        if profile.requests_in_window >= 4:
            raise HTTPException(429, "Please wait a minute before creating another set.")
        used = await db.scalar(
            select(func.coalesce(func.sum(PracticeAttempt.total_questions), 0)).where(
                PracticeAttempt.user_id == user.id,
                PracticeAttempt.question_mode.in_(["similar", "daily"]),
                PracticeAttempt.started_at
                >= now.replace(hour=0, minute=0, second=0, microsecond=0),
            )
        )
        reserved = await db.scalar(
            select(func.count())
            .select_from(DailyQuizPreparation)
            .join(DailyStudyTask)
            .join(DailyStudyPlan)
            .where(
                DailyStudyPlan.user_id == user.id,
                DailyQuizPreparation.attempt_id.is_(None),
                DailyQuizPreparation.created_at
                >= now.replace(hour=0, minute=0, second=0, microsecond=0),
            )
        )
        if used + reserved * 50 + 50 > get_settings().practice_ai_daily_questions:
            raise HTTPException(
                429,
                "Today's similar-practice limit is reached. "
                "You can still use the question bank or resume a saved quiz.",
            )
        bank = await choose_bank(db, user.id, task)
        if draft is None:
            draft = DailyQuizPreparation(task_id=task_id)
            db.add(draft)
        draft.bank_ids, draft.questions, draft.attempt_id = [q.id for q in bank], [], None
        draft.lease_token = draft.lease_until = None
        draft.created_at = now
        profile.requests_in_window += 1
        await db.commit()
        return progress(draft)

    if len(draft.bank_ids) + len(draft.questions) == 50:
        return await finish_draft(db, user, task, draft)
    if draft.lease_until and draft.lease_until.replace(tzinfo=UTC) > now:
        return progress(draft, waiting=True)
    profile = await locked_profile(db, user.id)
    if profile.busy_until and profile.busy_until.replace(tzinfo=UTC) > now:
        return progress(draft, waiting=True)
    if not profile.request_window_started or now - profile.request_window_started.replace(
        tzinfo=UTC
    ) >= timedelta(minutes=1):
        profile.request_window_started, profile.requests_in_window = now, 0
    if profile.requests_in_window >= 4:
        return progress(draft, waiting=True)
    profile.requests_in_window += 1
    lease = new_id()
    lease_until = now + timedelta(seconds=LEASE_SECONDS)
    draft.lease_token, draft.lease_until = lease, lease_until
    profile.busy_until = lease_until
    avoid = list(await db.scalars(select(Question.prompt).where(Question.id.in_(draft.bank_ids))))
    avoid += list(
        await db.scalars(
            select(Question.prompt)
            .where(
                Question.owner_user_id == user.id,
                Question.topic_id.in_(
                    select(Topic.id).where(
                        Topic.slug == task.topic_slug, Topic.subject.has(slug=task.subject_slug)
                    )
                ),
            )
            .order_by(Question.id)
            .limit(100)
        )
    )
    avoid += [q["prompt"] for q in draft.questions]
    count = min(BATCH_SIZE, 50 - len(draft.bank_ids) - len(draft.questions))
    await db.commit()  # Release locks and the connection before calling the AI.
    try:
        async with asyncio.timeout(STEP_SECONDS):
            items = await reviewed_batch(rag, task, count, avoid)
        if not items:
            raise RagUnavailableError("No checked questions in this batch")
        await db.execute(select(User.id).where(User.id == user.id).with_for_update())
        task = await ready_task(db, user.id, task_id)
        draft = await db.get(DailyQuizPreparation, task_id, populate_existing=True)
        if draft.lease_token != lease:
            return progress(draft, waiting=True)
        draft.questions = [*draft.questions, *items]
        draft.lease_token = draft.lease_until = None
        await db.execute(
            update(DoubtStudyProfile)
            .where(
                DoubtStudyProfile.user_id == user_id, DoubtStudyProfile.busy_until == lease_until
            )
            .values(busy_until=None)
        )
        await db.commit()
        return progress(draft)
    except (TimeoutError, RagUnavailableError) as exc:
        raise HTTPException(
            503,
            "We couldn't check the next questions right now. "
            "Your prepared questions are saved — retry to continue.",
        ) from exc
    finally:
        # Conditional release cannot unlock a newer worker after this lease expires.
        await db.rollback()
        await db.execute(
            update(DailyQuizPreparation)
            .where(
                DailyQuizPreparation.task_id == task_id, DailyQuizPreparation.lease_token == lease
            )
            .values(lease_token=None, lease_until=None)
        )
        await db.execute(
            update(DoubtStudyProfile)
            .where(
                DoubtStudyProfile.user_id == user_id, DoubtStudyProfile.busy_until == lease_until
            )
            .values(busy_until=None)
        )
        await db.commit()
