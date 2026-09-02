from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.auth import User
from app.models.papers import PaperAnswer, PaperAttempt, PaperQuestion, PreviousPaper
from app.models.practice import Subject
from app.schemas.papers import (
    CompletePaperAttemptRequest,
    PaperAnswerReviewResponse,
    PaperAttemptResponse,
    PaperAttemptSummaryResponse,
    PaperDetailResponse,
    PaperListItemResponse,
    PaperQuestionResponse,
    PaperSolutionResponse,
    SavedPaperAnswerResponse,
    SavePaperAnswerRequest,
)

router = APIRouter(tags=["previous papers"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def list_item(
    paper: PreviousPaper, available: int, verified: int
) -> PaperListItemResponse:
    return PaperListItemResponse(
        id=paper.id,
        year=paper.year,
        cycle=paper.cycle,
        title=paper.title,
        subject_slug=paper.subject.slug,
        subject_name=paper.subject.name,
        exam_date=paper.exam_date,
        duration_seconds=paper.duration_seconds,
        total_marks=paper.total_marks,
        official_question_count=paper.official_question_count,
        available_question_count=available,
        verified_question_count=verified,
        academy_tracks=paper.academy_tracks,
        source_url=paper.source_url,
        solutions_available=available > 0,
    )


@router.get("/papers", response_model=list[PaperListItemResponse])
async def list_papers(
    db: DatabaseSession,
    year: int | None = Query(default=None, ge=2000, le=2100),
    cycle: str | None = Query(default=None, pattern="^(I|II)$"),
    subject: str | None = None,
) -> list[PaperListItemResponse]:
    query = (
        select(PreviousPaper)
        .join(Subject, Subject.id == PreviousPaper.subject_id)
        .options(
            selectinload(PreviousPaper.subject),
            selectinload(PreviousPaper.questions),
        )
        .where(PreviousPaper.is_published.is_(True))
        .order_by(PreviousPaper.year.desc(), PreviousPaper.cycle, Subject.position)
    )
    if year is not None:
        query = query.where(PreviousPaper.year == year)
    if cycle is not None:
        query = query.where(PreviousPaper.cycle == cycle)
    if subject:
        query = query.where(Subject.slug == subject)
    papers = (await db.execute(query)).scalars().all()
    return [
        list_item(
            paper,
            len(paper.questions),
            sum(question.is_verified for question in paper.questions),
        )
        for paper in papers
    ]


async def get_paper_or_404(db: AsyncSession, paper_id: str) -> PreviousPaper:
    paper = (
        await db.execute(
            select(PreviousPaper)
            .options(
                selectinload(PreviousPaper.subject),
                selectinload(PreviousPaper.questions).selectinload(PaperQuestion.topic),
            )
            .where(PreviousPaper.id == paper_id, PreviousPaper.is_published.is_(True))
        )
    ).scalar_one_or_none()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


def public_question(question: PaperQuestion) -> PaperQuestionResponse:
    return PaperQuestionResponse(
        id=question.id,
        number=question.number,
        topic=question.topic.name if question.topic else None,
        prompt=question.prompt,
        context=question.context,
        options=question.options,
        asset_url=question.asset_url,
        is_verified=question.is_verified,
    )


@router.get("/papers/{paper_id}", response_model=PaperDetailResponse)
async def paper_detail(
    paper_id: str, _user: CurrentUser, db: DatabaseSession
) -> PaperDetailResponse:
    paper = await get_paper_or_404(db, paper_id)
    questions = list(paper.questions)
    item = list_item(
        paper,
        len(questions),
        sum(question.is_verified for question in questions),
    )
    return PaperDetailResponse(
        **item.model_dump(),
        negative_mark_fraction=paper.negative_mark_fraction,
        questions=[
            PaperSolutionResponse(
                **public_question(question).model_dump(),
                correct_index=question.correct_index if question.is_verified else None,
                explanation=question.explanation if question.is_verified else None,
                source_label=question.source_label,
            )
            for question in questions
        ],
    )


@router.post(
    "/papers/{paper_id}/attempts",
    response_model=PaperAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_paper_attempt(
    paper_id: str, user: CurrentUser, db: DatabaseSession
) -> PaperAttemptResponse:
    paper = await get_paper_or_404(db, paper_id)
    questions = [question for question in paper.questions if question.is_verified]
    if not questions:
        raise HTTPException(status_code=409, detail="Verified questions are not available yet")
    attempt = PaperAttempt(
        paper_id=paper.id,
        user_id=user.id,
        total_questions=len(questions),
    )
    db.add(attempt)
    await db.commit()
    return PaperAttemptResponse(
        id=attempt.id,
        paper_id=paper.id,
        title=paper.title,
        started_at=attempt.started_at,
        duration_seconds=paper.duration_seconds,
        questions=[public_question(question) for question in questions],
    )


async def owned_active_attempt(db: AsyncSession, attempt_id: str, user_id: str) -> PaperAttempt:
    attempt = (
        await db.execute(
            select(PaperAttempt).where(
                PaperAttempt.id == attempt_id, PaperAttempt.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Paper attempt not found")
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="This paper attempt is already complete")
    return attempt


@router.put(
    "/paper-attempts/{attempt_id}/answers/{question_id}",
    response_model=SavedPaperAnswerResponse,
)
async def save_paper_answer(
    attempt_id: str,
    question_id: str,
    payload: SavePaperAnswerRequest,
    user: CurrentUser,
    db: DatabaseSession,
) -> SavedPaperAnswerResponse:
    attempt = await owned_active_attempt(db, attempt_id, user.id)
    question = (
        await db.execute(
            select(PaperQuestion).where(
                PaperQuestion.id == question_id,
                PaperQuestion.paper_id == attempt.paper_id,
                PaperQuestion.is_verified.is_(True),
            )
        )
    ).scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question is not part of this paper")
    if payload.selected_index >= len(question.options):
        raise HTTPException(status_code=422, detail="Selected option is invalid")
    answer = (
        await db.execute(
            select(PaperAnswer).where(
                PaperAnswer.attempt_id == attempt.id,
                PaperAnswer.question_id == question.id,
            )
        )
    ).scalar_one_or_none()
    if answer is None:
        answer = PaperAnswer(attempt_id=attempt.id, question_id=question.id)
        db.add(answer)
    answer.selected_index = payload.selected_index
    answer.is_correct = payload.selected_index == question.correct_index
    answer.marked_for_review = payload.marked_for_review
    answer.answered_at = datetime.now(UTC)
    await db.commit()
    return SavedPaperAnswerResponse(
        question_id=question.id,
        selected_index=answer.selected_index,
        marked_for_review=answer.marked_for_review,
    )


@router.post(
    "/paper-attempts/{attempt_id}/complete",
    response_model=PaperAttemptSummaryResponse,
)
async def complete_paper_attempt(
    attempt_id: str,
    payload: CompletePaperAttemptRequest,
    user: CurrentUser,
    db: DatabaseSession,
) -> PaperAttemptSummaryResponse:
    attempt = await owned_active_attempt(db, attempt_id, user.id)
    paper = await get_paper_or_404(db, attempt.paper_id)
    questions = [question for question in paper.questions if question.is_verified]
    answers = {
        answer.question_id: answer
        for answer in (
            await db.execute(select(PaperAnswer).where(PaperAnswer.attempt_id == attempt.id))
        ).scalars()
    }
    correct = sum(1 for answer in answers.values() if answer.is_correct)
    incorrect = len(answers) - correct
    unanswered = len(questions) - len(answers)
    score = round(correct - incorrect * paper.negative_mark_fraction, 2)
    attempt.status = "completed"
    attempt.correct_answers = correct
    attempt.score = score
    attempt.duration_seconds = payload.duration_seconds
    attempt.completed_at = datetime.now(UTC)
    await db.commit()
    return PaperAttemptSummaryResponse(
        attempt_id=attempt.id,
        total_questions=len(questions),
        answered_questions=len(answers),
        correct_answers=correct,
        incorrect_answers=incorrect,
        unanswered_questions=unanswered,
        score=score,
        accuracy=round(correct * 100 / len(questions), 1),
        duration_seconds=payload.duration_seconds,
        review=[
            PaperAnswerReviewResponse(
                question_id=question.id,
                selected_index=answers[question.id].selected_index
                if question.id in answers
                else None,
                correct_index=question.correct_index,
                is_correct=answers[question.id].is_correct if question.id in answers else False,
                explanation=question.explanation,
                source_label=question.source_label,
            )
            for question in questions
        ],
    )
