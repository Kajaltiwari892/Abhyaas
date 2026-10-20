"""Prepare a full quiz in durable, bounded steps, not one long HTTP request.

Each accepted batch is committed before replying. Repeating a request, losing
the response or moving to another server instance never creates a second quiz.
No in-process background tasks are used: serverless instances can stop safely.
"""

import asyncio
import json
import logging
import math
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
    PracticeAttempt,
    Question,
    Topic,
    new_id,
)
from app.models.rag import DoubtStudyProfile
from app.models.study_plan import DailyQuizPreparation, DailyStudyPlan, DailyStudyTask
from app.schemas.study_plan import DailyQuizPreparationResponse
from app.services.daily_quiz import ready_task
from app.services.practice_sets import PracticeQuestion
from app.services.prepared_question_pool import choose_prepared_questions, top_up_prepared_bank
from app.services.rag import RagService, RagUnavailableError
from app.services.study_memory import locked_profile

BATCH_SIZE = 10
STEP_SECONDS = 35
LEASE_SECONDS = 50
MAX_PHASE_FAILURES = 3
logger = logging.getLogger(__name__)


def fingerprint(prompt: str) -> str:
    return re.sub(r"\W+", "", prompt).casefold()


def progress(draft: DailyQuizPreparation, *, waiting: bool = False):
    retry_ms = 2000 if waiting else 0
    if draft.next_retry_at:
        retry_ms = max(
            retry_ms,
            math.ceil(
                (draft.next_retry_at.replace(tzinfo=UTC) - datetime.now(UTC)).total_seconds() * 1000
            ),
        )
    return DailyQuizPreparationResponse(
        status="preparing",
        prepared_count=len(draft.bank_ids) + len(draft.questions),
        retry_after_ms=retry_ms,
        phase="waiting" if waiting else "checking" if draft.pending_questions else "generating",
        message=(
            "The question service is busy. Your checked questions are saved; "
            "we'll try again shortly."
            if draft.failure_count
            else None
        ),
    )


async def choose_bank(db: AsyncSession, user_id: str, task) -> list[Question]:
    return await choose_prepared_questions(db, user_id, task)


async def generate_batch(rag: RagService, task, count: int, avoid: list[str]) -> list[dict]:
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
    return candidates


async def review_batch(rag: RagService, task, candidates: list[dict]) -> list[dict]:
    focus = task.topic_name + ". Focus only on: " + "; ".join(task.focus_points or [])
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
            provenance={
                "kind": "generated",
                "answer_verified": False,
                "curriculum_key": task.curriculum_key,
                "review_status": "independent_ai_checked",
            },
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
        draft.pending_questions, draft.failure_count, draft.next_retry_at = [], 0, None
        draft.lease_token = draft.lease_until = None
        draft.created_at = now
        profile.requests_in_window += 1
        if len(bank) == 50:
            return await finish_draft(db, user, task, draft)
        await db.commit()
        return progress(draft)

    if len(draft.bank_ids) + len(draft.questions) == 50:
        return await finish_draft(db, user, task, draft)
    if draft.lease_until and draft.lease_until.replace(tzinfo=UTC) > now:
        return progress(draft, waiting=True)
    topped_up = await top_up_prepared_bank(db, user_id, task, draft)
    if topped_up and len(draft.bank_ids) + len(draft.questions) == 50:
        return await finish_draft(db, user, task, draft)
    if draft.next_retry_at and draft.next_retry_at.replace(tzinfo=UTC) > now:
        if topped_up:
            await db.commit()
        return progress(draft, waiting=True)
    profile = await locked_profile(db, user.id)
    if profile.busy_until and profile.busy_until.replace(tzinfo=UTC) > now:
        if topped_up:
            await db.commit()
        return progress(draft, waiting=True)
    # The creation quota was charged when this draft was reserved. Advancing its
    # phases is not a new set and must not consume the four-new-sets rate limit.
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
    checking = bool(draft.pending_questions)
    pending = list(draft.pending_questions)
    await db.commit()  # Release locks and the connection before calling the AI.
    review_rejected = False
    try:
        async with asyncio.timeout(STEP_SECONDS):
            items = (
                await review_batch(rag, task, pending)
                if checking
                else await generate_batch(rag, task, count, avoid)
            )
        if not items and not checking:
            raise RagUnavailableError("No valid candidate questions in this batch")
        if checking and not items:
            review_rejected = True
            raise RagUnavailableError("No reliable questions passed independent review")
        await db.execute(select(User.id).where(User.id == user_id).with_for_update())
        task = await ready_task(db, user_id, task_id)
        draft = await db.get(DailyQuizPreparation, task_id, populate_existing=True)
        if draft.lease_token != lease:
            return progress(draft, waiting=True)
        if checking:
            draft.questions = [*draft.questions, *items]
            draft.pending_questions = []
        else:
            # Commit this provider result before making any review request. A
            # later timeout or another server instance resumes review, not generation.
            draft.pending_questions = items
        # Only checked progress proves recovery. A provider that generates valid
        # JSON but repeatedly fails review must not reset this bounded retry count.
        if checking:
            draft.failure_count = 0
        draft.next_retry_at = None
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
        await db.rollback()
        await db.execute(select(User.id).where(User.id == user_id).with_for_update())
        draft = await db.get(DailyQuizPreparation, task_id, populate_existing=True)
        if draft.lease_token != lease:
            return progress(draft, waiting=True)
        if review_rejected:
            # This review completed and rejected every candidate. Do not endlessly
            # re-review known unusable questions; replace them after bounded backoff.
            draft.pending_questions = []
        draft.failure_count += 1
        draft.next_retry_at = datetime.now(UTC) + timedelta(
            seconds=min(30, 5 * 2 ** min(draft.failure_count - 1, 3))
        )
        draft.lease_token = draft.lease_until = None
        await db.commit()
        logger.warning(
            "Daily quiz %s phase unavailable: %s", "review" if checking else "generation", exc
        )
        if draft.failure_count >= MAX_PHASE_FAILURES:
            detail = (
                "Reliable questions aren't available for this lesson right now. "
                "Your checked questions are saved. Please try again later."
                if review_rejected
                else "The question service is busy, not your connection. Your prepared questions "
                "are saved. Please try again later."
            )
            raise HTTPException(
                503,
                detail,
                headers={"Retry-After": "30"},
            ) from exc
        return progress(draft)
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
