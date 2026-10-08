"""Full, private daily quizzes: genuine sourced PYQs plus reviewed new practice."""

import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.practice import PracticeAnswer, Question, Subject, Topic
from app.schemas.practice import StartSimilarAttemptRequest
from app.services.rag import RagService
from app.services.similar_practice import create_similar_attempt
from app.services.study_curriculum import Unit, find_unit
from app.services.study_plan import owned_task, require_today, task_view


async def ready_task(db: AsyncSession, user_id: str, task_id: str):
    task = await owned_task(db, user_id, task_id)
    require_today(task)
    if not task.study_done_at or task.deferred_at:
        raise HTTPException(409, "Mark your study as done before taking today's quiz.")
    if task_view(task, task.plan.plan_date).completed:
        raise HTTPException(
            409, "Today's target is complete. You can review your result in History."
        )
    return task


def matches_lesson(question: Question, lesson: Unit) -> bool:
    # Shared paper directions mention many skills. They must not turn every
    # grammar question into an agreement question or every GK item into geography.
    text = " ".join([question.prompt, str((question.provenance or {}).get("chapter", ""))]).lower()
    if lesson.key == "reading":
        text += " " + (question.context or "").lower()
    if lesson.key == "agreement":
        if re.search(r"\bagreement\b", text):
            return True
        if not re.search(r"\b(?:neither|either|each|every|everyone|anyone|nobody)\b", text):
            return False
        # Quantifier blanks alone test determiners, not subject–verb agreement.
        return any(
            re.search(r"\b(?:is|are|was|were|has|have|do|does)\b", str(option), re.I)
            for option in question.options
        )
    return any(re.search(r"\b" + re.escape(term), text) for term in lesson.terms)


async def start_daily_quiz(db: AsyncSession, user: User, task_id: str, rag: RagService):
    from app.api.v1.practice import get_attempt

    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    task = await ready_task(db, user.id, task_id)
    if task.quiz_attempt and task.quiz_attempt.status == "in_progress":
        return await get_attempt(task.quiz_attempt.id, user, db)
    unit = find_unit(task.curriculum_key)
    bank_topics = [task.topic_slug]
    if task.subject_slug == "english" and task.topic_slug in {"grammar", "error-spotting"}:
        bank_topics = ["grammar", "error-spotting"]
    rows = list(
        await db.scalars(
            select(Question)
            .join(Topic)
            .join(Subject)
            .where(
                Subject.slug == task.subject_slug,
                Topic.slug.in_(bank_topics),
                Question.owner_user_id.is_(None),
                Question.is_active.is_(True),
                ~Question.id.in_(
                    select(PracticeAnswer.question_id)
                    .join(PracticeAnswer.attempt)
                    .where(PracticeAnswer.attempt.has(user_id=user.id))
                ),
            )
            .order_by(Question.id)
        )
    )
    bank = []
    fingerprints = set()
    for q in rows:
        p = q.provenance or {}
        if (
            p.get("kind") != "pyq"
            or not p.get("paper_question_id")
            or not p.get("source_url")
            or not 0 <= q.correct_index < len(q.options)
        ):
            continue
        if unit and not matches_lesson(q, unit):
            continue
        fingerprint = re.sub(r"\s+", " ", q.prompt).strip().casefold()
        if fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        bank.append(q)
        if len(bank) == 20:
            break
    return await create_similar_attempt(
        db,
        user.id,
        StartSimilarAttemptRequest(
            subject_slug=task.subject_slug,
            topic_slug=task.topic_slug,
            question_count=50 - len(bank),
            focus_detail=task.topic_name + ". Focus only on: " + "; ".join(task.focus_points or []),
        ),
        rag,
        daily_task_id=task.id,
        bank_questions=bank,
    )
