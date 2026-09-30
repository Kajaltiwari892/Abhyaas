from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.auth import User
from app.models.practice import (
    AttemptQuestion,
    PracticeAnswer,
    PracticeAttempt,
    Question,
    Subject,
    Topic,
)
from app.schemas.practice import (
    AnswerReviewResponse,
    AttemptAnswerInput,
    AttemptResponse,
    AttemptSummaryResponse,
    CatalogQuestionPage,
    CompleteAttemptRequest,
    PracticeAvailability,
    PracticeHistoryItem,
    PracticeHistoryPage,
    PracticeQuestionResponse,
    SaveAnswerRequest,
    SavedAnswerResponse,
    StartAttemptRequest,
    SubjectResponse,
    TopicResponse,
)

router = APIRouter(tags=["practice"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/catalog/subjects", response_model=list[SubjectResponse])
async def list_subjects(db: DatabaseSession) -> list[SubjectResponse]:
    counts = dict(
        (
            await db.execute(
                select(Question.topic_id, func.count(Question.id))
                .where(Question.is_active.is_(True))
                .group_by(Question.topic_id)
            )
        ).all()
    )
    result = await db.execute(
        select(Subject).options(selectinload(Subject.topics)).order_by(Subject.position)
    )
    return [
        SubjectResponse(
            id=subject.id,
            slug=subject.slug,
            code=subject.code,
            name=subject.name,
            description=subject.description,
            question_count=sum(counts.get(topic.id, 0) for topic in subject.topics),
            topics=[
                TopicResponse(
                    id=topic.id,
                    slug=topic.slug,
                    name=topic.name,
                    question_count=counts.get(topic.id, 0),
                )
                for topic in subject.topics
            ],
        )
        for subject in result.scalars().all()
    ]


@router.get("/catalog/questions", response_model=CatalogQuestionPage)
async def catalog_questions(
    db: DatabaseSession,
    subject_slug: str,
    topic_slug: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=20),
) -> CatalogQuestionPage:
    subject = (
        await db.execute(select(Subject).where(Subject.slug == subject_slug))
    ).scalar_one_or_none()
    if subject is None:
        raise HTTPException(404, "Subject not found")
    filters = [Topic.subject_id == subject.id, Question.is_active.is_(True)]
    if topic_slug:
        topic = (
            await db.execute(
                select(Topic).where(Topic.subject_id == subject.id, Topic.slug == topic_slug)
            )
        ).scalar_one_or_none()
        if topic is None:
            raise HTTPException(404, "Topic not found for this subject")
        filters.append(Question.topic_id == topic.id)
    total = (
        await db.execute(select(func.count(Question.id)).join(Topic).where(*filters))
    ).scalar_one()
    rows = (
        await db.execute(
            select(Question, Topic)
            .join(Topic)
            .where(*filters)
            .order_by(Topic.position, Question.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return CatalogQuestionPage(
        total=total,
        has_more=offset + len(rows) < total,
        questions=[
            PracticeQuestionResponse(
                id=q.id,
                position=offset + i + 1,
                subject=subject.name,
                topic=t.name,
                prompt=q.prompt,
                context=q.context,
                options=q.options,
                source_label=q.source_label,
                provenance=q.provenance,
            )
            for i, (q, t) in enumerate(rows)
        ],
    )


@router.post(
    "/practice/attempts", response_model=AttemptResponse, status_code=status.HTTP_201_CREATED
)
async def start_attempt(
    payload: StartAttemptRequest, user: CurrentUser, db: DatabaseSession
) -> AttemptResponse:
    # Serialize set allocation for a student, including requests from two tabs.
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    subject = (
        await db.execute(select(Subject).where(Subject.slug == payload.subject_slug))
    ).scalar_one_or_none()
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")

    topic: Topic | None = None
    query = (
        select(Question)
        .join(Topic)
        .where(Topic.subject_id == subject.id, Question.is_active.is_(True))
    )
    if payload.topic_slug:
        topic = (
            await db.execute(
                select(Topic).where(
                    Topic.subject_id == subject.id, Topic.slug == payload.topic_slug
                )
            )
        ).scalar_one_or_none()
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic not found for this subject")
        query = query.where(Question.topic_id == topic.id)

    # A question assigned to any of this student's sets is considered seen, even if skipped.
    # This prevents repeatedly handing out the same tiny pool under different set-size labels.
    seen = seen_question_counts(user.id)
    query = query.outerjoin(seen, seen.c.question_id == Question.id)
    if not payload.allow_repeats:
        query = query.where(seen.c.question_id.is_(None))
    questions = list(
        (
            await db.execute(
                query.order_by(
                    func.coalesce(seen.c.times_seen, 0), seen.c.last_seen.asc(), func.random()
                ).limit(payload.question_count)
            )
        ).scalars()
    )
    if not questions:
        raise HTTPException(
            status_code=409,
            detail=(
                "No new questions remain for this selection. "
                "Resume a saved set or choose revision mode."
            ),
        )
    seen_ids = set((await db.execute(select(seen.c.question_id))).scalars())
    repeats = sum(q.id in seen_ids for q in questions)

    attempt = PracticeAttempt(
        user_id=user.id,
        subject_id=subject.id,
        topic_id=topic.id if topic else None,
        total_questions=len(questions),
        time_limit_seconds=len(questions)
        * (72 if subject.slug == "elementary-mathematics" else 60),
        negative_mark_fraction=1 / 3,
    )
    db.add(attempt)
    await db.flush()
    for position, question in enumerate(questions, start=1):
        db.add(AttemptQuestion(attempt_id=attempt.id, question_id=question.id, position=position))
    await db.commit()

    topic_by_id = {
        item.id: item
        for item in (
            await db.execute(select(Topic).where(Topic.subject_id == subject.id))
        ).scalars()
    }
    return AttemptResponse(
        id=attempt.id,
        subject=subject.name,
        subject_slug=subject.slug,
        topic=topic.name if topic else None,
        topic_slug=topic.slug if topic else None,
        started_at=attempt.started_at,
        duration_seconds=attempt.time_limit_seconds,
        negative_mark_fraction=attempt.negative_mark_fraction,
        new_questions=len(questions) - repeats,
        repeated_questions=repeats,
        questions=[
            PracticeQuestionResponse(
                id=question.id,
                position=position,
                subject=subject.name,
                topic=topic_by_id[question.topic_id].name,
                prompt=question.prompt,
                context=question.context,
                options=question.options,
                source_label=question.source_label,
                provenance=question.provenance,
            )
            for position, question in enumerate(questions, start=1)
        ],
    )


def seen_question_counts(user_id: str):
    return (
        select(
            AttemptQuestion.question_id,
            func.count().label("times_seen"),
            func.max(PracticeAttempt.started_at).label("last_seen"),
        )
        .join(PracticeAttempt, PracticeAttempt.id == AttemptQuestion.attempt_id)
        .where(PracticeAttempt.user_id == user_id)
        .group_by(AttemptQuestion.question_id)
        .subquery()
    )


@router.get("/practice/availability", response_model=PracticeAvailability)
async def practice_availability(
    user: CurrentUser,
    db: DatabaseSession,
    subject_slug: str,
    topic_slug: str | None = None,
) -> PracticeAvailability:
    seen = seen_question_counts(user.id)
    query = (
        select(Question.id, seen.c.question_id)
        .select_from(Question)
        .join(Topic, Topic.id == Question.topic_id)
        .join(Subject, Subject.id == Topic.subject_id)
        .outerjoin(seen, seen.c.question_id == Question.id)
        .where(Subject.slug == subject_slug, Question.is_active.is_(True))
    )
    if topic_slug:
        query = query.where(Topic.slug == topic_slug)
    rows = (await db.execute(query)).all()
    unseen = sum(seen_id is None for _, seen_id in rows)
    return PracticeAvailability(total=len(rows), unseen=unseen, seen=len(rows) - unseen)


async def owned_attempt(db: AsyncSession, attempt_id: str, user_id: str) -> PracticeAttempt:
    attempt = (
        await db.execute(
            select(PracticeAttempt)
            .options(selectinload(PracticeAttempt.subject), selectinload(PracticeAttempt.topic))
            .where(PracticeAttempt.id == attempt_id, PracticeAttempt.user_id == user_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Practice attempt not found")
    return attempt


async def owned_active_attempt(db: AsyncSession, attempt_id: str, user_id: str) -> PracticeAttempt:
    attempt = await owned_attempt(db, attempt_id, user_id)
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="This practice attempt is already complete")
    return attempt


@router.get("/practice/attempts", response_model=PracticeHistoryPage)
async def attempt_history(
    user: CurrentUser,
    db: DatabaseSession,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
) -> PracticeHistoryPage:
    total = (
        await db.execute(
            select(func.count(PracticeAttempt.id)).where(PracticeAttempt.user_id == user.id)
        )
    ).scalar_one()
    attempts = list(
        (
            await db.execute(
                select(PracticeAttempt)
                .options(
                    selectinload(PracticeAttempt.subject),
                    selectinload(PracticeAttempt.topic),
                    selectinload(PracticeAttempt.answers),
                )
                .where(PracticeAttempt.user_id == user.id)
                .order_by(PracticeAttempt.started_at.desc(), PracticeAttempt.id.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars()
    )
    return PracticeHistoryPage(
        total=total,
        has_more=offset + len(attempts) < total,
        items=[
            PracticeHistoryItem(
                id=a.id,
                subject=a.subject.name,
                topic=a.topic.name if a.topic else None,
                status=a.status,
                started_at=a.started_at,
                completed_at=a.completed_at,
                total_questions=a.total_questions,
                answered_questions=len(a.answers),
                correct_answers=a.correct_answers,
                duration_seconds=a.duration_seconds or 0,
                time_limit_seconds=a.time_limit_seconds,
            )
            for a in attempts
        ],
    )


@router.get("/practice/attempts/{attempt_id}", response_model=AttemptResponse)
async def get_attempt(attempt_id: str, user: CurrentUser, db: DatabaseSession) -> AttemptResponse:
    attempt = await owned_attempt(db, attempt_id, user.id)
    rows = (
        await db.execute(
            select(AttemptQuestion, Question, Topic)
            .join(Question, Question.id == AttemptQuestion.question_id)
            .join(Topic, Topic.id == Question.topic_id)
            .where(AttemptQuestion.attempt_id == attempt.id)
            .order_by(AttemptQuestion.position)
        )
    ).all()
    answers = (
        await db.execute(select(PracticeAnswer).where(PracticeAnswer.attempt_id == attempt.id))
    ).scalars()
    return AttemptResponse(
        id=attempt.id,
        subject=attempt.subject.name,
        subject_slug=attempt.subject.slug,
        topic=attempt.topic.name if attempt.topic else None,
        topic_slug=attempt.topic.slug if attempt.topic else None,
        status=attempt.status,
        started_at=attempt.started_at,
        elapsed_seconds=attempt.duration_seconds or 0,
        duration_seconds=attempt.time_limit_seconds,
        current_position=attempt.current_position,
        negative_mark_fraction=attempt.negative_mark_fraction,
        answers=[
            SavedAnswerResponse(
                question_id=a.question_id,
                selected_index=a.selected_index,
                marked_for_review=a.marked_for_review,
            )
            for a in answers
        ],
        questions=[
            PracticeQuestionResponse(
                id=q.id,
                position=aq.position,
                subject=attempt.subject.name,
                topic=t.name,
                prompt=q.prompt,
                context=q.context,
                options=q.options,
                source_label=q.source_label,
                provenance=q.provenance,
            )
            for aq, q, t in rows
        ],
    )


async def save_answer_batch(
    db: AsyncSession, attempt: PracticeAttempt, inputs: list[AttemptAnswerInput]
) -> None:
    questions = {
        q.id: q
        for q in (
            await db.execute(
                select(Question)
                .join(AttemptQuestion)
                .where(AttemptQuestion.attempt_id == attempt.id)
            )
        ).scalars()
    }
    if len({item.question_id for item in inputs}) != len(inputs):
        raise HTTPException(422, "Duplicate question answers")
    for item in inputs:
        if item.question_id not in questions:
            raise HTTPException(422, "Question is not part of this attempt")
        if item.selected_index >= len(questions[item.question_id].options):
            raise HTTPException(422, "Selected option is invalid")
    saved = {
        a.question_id: a
        for a in (
            await db.execute(select(PracticeAnswer).where(PracticeAnswer.attempt_id == attempt.id))
        ).scalars()
    }
    for item in inputs:
        answer = saved.get(item.question_id)
        if answer is None:
            answer = PracticeAnswer(attempt_id=attempt.id, question_id=item.question_id)
            db.add(answer)
        answer.selected_index = item.selected_index
        answer.marked_for_review = item.marked_for_review
        answer.is_correct = item.selected_index == questions[item.question_id].correct_index
        answer.answered_at = datetime.now(UTC)
    await db.flush()


@router.patch("/practice/attempts/{attempt_id}", response_model=None)
async def checkpoint_attempt(
    attempt_id: str,
    payload: CompleteAttemptRequest,
    user: CurrentUser,
    db: DatabaseSession,
) -> None:
    attempt = await owned_active_attempt(db, attempt_id, user.id)
    await save_answer_batch(db, attempt, payload.answers)
    apply_checkpoint(attempt, payload)
    await db.commit()


def apply_checkpoint(attempt: PracticeAttempt, payload: CompleteAttemptRequest) -> None:
    if payload.current_position is not None:
        if payload.current_position >= attempt.total_questions:
            raise HTTPException(422, "Question position is outside this set")
        attempt.current_position = payload.current_position
    attempt.duration_seconds = min(
        attempt.time_limit_seconds, max(attempt.duration_seconds or 0, payload.duration_seconds)
    )


@router.put(
    "/practice/attempts/{attempt_id}/answers/{question_id}",
    response_model=SavedAnswerResponse,
)
async def save_answer(
    attempt_id: str,
    question_id: str,
    payload: SaveAnswerRequest,
    user: CurrentUser,
    db: DatabaseSession,
) -> SavedAnswerResponse:
    await owned_active_attempt(db, attempt_id, user.id)
    question = (
        await db.execute(
            select(Question)
            .join(AttemptQuestion, AttemptQuestion.question_id == Question.id)
            .where(
                AttemptQuestion.attempt_id == attempt_id,
                AttemptQuestion.question_id == question_id,
            )
        )
    ).scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question is not part of this attempt")
    if payload.selected_index >= len(question.options):
        raise HTTPException(status_code=422, detail="Selected option is invalid")

    answer = (
        await db.execute(
            select(PracticeAnswer).where(
                PracticeAnswer.attempt_id == attempt_id,
                PracticeAnswer.question_id == question_id,
            )
        )
    ).scalar_one_or_none()
    if answer is None:
        answer = PracticeAnswer(attempt_id=attempt_id, question_id=question_id)
        db.add(answer)
    answer.selected_index = payload.selected_index
    answer.is_correct = payload.selected_index == question.correct_index
    answer.marked_for_review = payload.marked_for_review
    answer.answered_at = datetime.now(UTC)
    await db.commit()
    return SavedAnswerResponse(
        question_id=question_id,
        selected_index=answer.selected_index,
        marked_for_review=answer.marked_for_review,
    )


@router.post("/practice/attempts/{attempt_id}/complete", response_model=AttemptSummaryResponse)
async def complete_attempt(
    attempt_id: str,
    payload: CompleteAttemptRequest,
    user: CurrentUser,
    db: DatabaseSession,
) -> AttemptSummaryResponse:
    attempt = await owned_attempt(db, attempt_id, user.id)
    if attempt.status == "completed":
        return await build_summary(db, attempt)
    await save_answer_batch(db, attempt, payload.answers)
    correct = (
        await db.execute(
            select(func.count(PracticeAnswer.id)).where(
                PracticeAnswer.attempt_id == attempt.id, PracticeAnswer.is_correct.is_(True)
            )
        )
    ).scalar_one()
    attempt.status = "completed"
    attempt.correct_answers = correct
    apply_checkpoint(attempt, payload)
    attempt.completed_at = datetime.now(UTC)
    await db.commit()
    return await build_summary(db, attempt)


@router.get("/practice/attempts/{attempt_id}/result", response_model=AttemptSummaryResponse)
async def attempt_result(
    attempt_id: str, user: CurrentUser, db: DatabaseSession
) -> AttemptSummaryResponse:
    attempt = await owned_attempt(db, attempt_id, user.id)
    if attempt.status != "completed":
        raise HTTPException(409, "Finish this set to see the result")
    return await build_summary(db, attempt)


async def build_summary(db: AsyncSession, attempt: PracticeAttempt) -> AttemptSummaryResponse:
    question_rows = (
        await db.execute(
            select(AttemptQuestion, Question, Topic)
            .join(Question, Question.id == AttemptQuestion.question_id)
            .join(Topic, Topic.id == Question.topic_id)
            .where(AttemptQuestion.attempt_id == attempt.id)
            .order_by(AttemptQuestion.position)
        )
    ).all()
    answers = {
        answer.question_id: answer
        for answer in (
            await db.execute(select(PracticeAnswer).where(PracticeAnswer.attempt_id == attempt.id))
        ).scalars()
    }
    correct = sum(1 for answer in answers.values() if answer.is_correct)

    review = [
        AnswerReviewResponse(
            question_id=question.id,
            selected_index=answers[question.id].selected_index if question.id in answers else None,
            correct_index=question.correct_index,
            is_correct=answers[question.id].is_correct if question.id in answers else False,
            explanation=question.explanation,
            source_label=question.source_label,
            position=aq.position,
            prompt=question.prompt,
            context=question.context,
            options=question.options,
            topic=topic.name,
            provenance=question.provenance,
        )
        for aq, question, topic in question_rows
    ]
    return AttemptSummaryResponse(
        attempt_id=attempt.id,
        subject=attempt.subject.name,
        topic=attempt.topic.name if attempt.topic else None,
        total_questions=attempt.total_questions,
        answered_questions=len(answers),
        correct_answers=correct,
        accuracy=round(correct * 100 / attempt.total_questions, 1),
        duration_seconds=attempt.duration_seconds or 0,
        score=round(correct - (len(answers) - correct) * attempt.negative_mark_fraction, 2),
        negative_mark_fraction=attempt.negative_mark_fraction,
        review=review,
    )
