from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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
    AttemptResponse,
    AttemptSummaryResponse,
    CompleteAttemptRequest,
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
            topics=[
                TopicResponse(id=topic.id, slug=topic.slug, name=topic.name)
                for topic in subject.topics
            ],
        )
        for subject in result.scalars().all()
    ]


@router.post(
    "/practice/attempts", response_model=AttemptResponse, status_code=status.HTTP_201_CREATED
)
async def start_attempt(
    payload: StartAttemptRequest, user: CurrentUser, db: DatabaseSession
) -> AttemptResponse:
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

    questions = list(
        (await db.execute(query.order_by(func.random()).limit(payload.question_count))).scalars()
    )
    if not questions:
        raise HTTPException(status_code=409, detail="No practice questions are available yet")

    attempt = PracticeAttempt(
        user_id=user.id,
        subject_id=subject.id,
        topic_id=topic.id if topic else None,
        total_questions=len(questions),
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
        topic=topic.name if topic else None,
        started_at=attempt.started_at,
        questions=[
            PracticeQuestionResponse(
                id=question.id,
                position=position,
                subject=subject.name,
                topic=topic_by_id[question.topic_id].name,
                prompt=question.prompt,
                context=question.context,
                options=question.options,
            )
            for position, question in enumerate(questions, start=1)
        ],
    )


async def owned_active_attempt(db: AsyncSession, attempt_id: str, user_id: str) -> PracticeAttempt:
    attempt = (
        await db.execute(
            select(PracticeAttempt).where(
                PracticeAttempt.id == attempt_id, PracticeAttempt.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Practice attempt not found")
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="This practice attempt is already complete")
    return attempt


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
    attempt = await owned_active_attempt(db, attempt_id, user.id)
    question_rows = (
        await db.execute(
            select(AttemptQuestion, Question)
            .join(Question, Question.id == AttemptQuestion.question_id)
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
    attempt.status = "completed"
    attempt.correct_answers = correct
    attempt.duration_seconds = payload.duration_seconds
    attempt.completed_at = datetime.now(UTC)
    await db.commit()

    review = [
        AnswerReviewResponse(
            question_id=question.id,
            selected_index=answers[question.id].selected_index if question.id in answers else None,
            correct_index=question.correct_index,
            is_correct=answers[question.id].is_correct if question.id in answers else False,
            explanation=question.explanation,
            source_label=question.source_label,
        )
        for _, question in question_rows
    ]
    return AttemptSummaryResponse(
        attempt_id=attempt.id,
        total_questions=attempt.total_questions,
        answered_questions=len(answers),
        correct_answers=correct,
        accuracy=round(correct * 100 / attempt.total_questions, 1),
        duration_seconds=payload.duration_seconds,
        review=review,
    )
