from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.auth import User
from app.models.papers import PaperAttempt, PreviousPaper
from app.models.practice import PracticeAttempt, Subject
from app.schemas.practice import (
    HistoryItemResponse,
    ProgressDashboardResponse,
    SubjectStrengthResponse,
    TrendPointResponse,
)
from app.services.paper_answers import grade_paper

router = APIRouter(tags=["progress"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass
class CompletedResult:
    id: str
    subject_id: str
    subject_name: str
    topic_name: str | None
    completed_at: datetime
    correct_answers: int
    total_questions: int
    scored_questions: int
    duration_seconds: int


@router.get("/progress/dashboard", response_model=ProgressDashboardResponse)
async def progress_dashboard(user: CurrentUser, db: DatabaseSession) -> ProgressDashboardResponse:
    subjects = list((await db.execute(select(Subject).order_by(Subject.position))).scalars())
    attempts = list(
        (
            await db.execute(
                select(PracticeAttempt)
                .options(selectinload(PracticeAttempt.subject), selectinload(PracticeAttempt.topic))
                .where(
                    PracticeAttempt.user_id == user.id,
                    PracticeAttempt.status == "completed",
                )
                .order_by(PracticeAttempt.completed_at.desc())
            )
        ).scalars()
    )
    paper_attempts = list(
        (
            await db.execute(
                select(PaperAttempt)
                .options(
                    selectinload(PaperAttempt.paper).selectinload(PreviousPaper.subject),
                    selectinload(PaperAttempt.paper).selectinload(PreviousPaper.questions),
                    selectinload(PaperAttempt.answers),
                )
                .where(
                    PaperAttempt.user_id == user.id,
                    PaperAttempt.status == "completed",
                )
                .order_by(PaperAttempt.completed_at.desc())
            )
        ).scalars()
    )
    paper_grades = {
        attempt.id: grade_paper(attempt.paper, list(attempt.paper.questions), list(attempt.answers))
        for attempt in paper_attempts
    }
    results = [
        CompletedResult(
            id=attempt.id,
            subject_id=attempt.subject_id,
            subject_name=attempt.subject.name,
            topic_name=attempt.topic.name if attempt.topic else None,
            completed_at=attempt.completed_at,
            correct_answers=attempt.correct_answers or 0,
            total_questions=attempt.total_questions,
            scored_questions=attempt.total_questions,
            duration_seconds=attempt.duration_seconds or 0,
        )
        for attempt in attempts
        if attempt.completed_at is not None
    ] + [
        CompletedResult(
            id=attempt.id,
            subject_id=attempt.paper.subject_id,
            subject_name=attempt.paper.subject.name,
            topic_name="Previous paper",
            completed_at=attempt.completed_at,
            correct_answers=paper_grades[attempt.id]["correct"],
            total_questions=attempt.total_questions,
            scored_questions=len(paper_grades[attempt.id]["keys"]),
            duration_seconds=attempt.duration_seconds or 0,
        )
        for attempt in paper_attempts
        if attempt.completed_at is not None
    ]
    results.sort(key=lambda result: result.completed_at, reverse=True)
    total_questions = sum(result.total_questions for result in results)
    total_scored = sum(result.scored_questions for result in results)
    total_correct = sum(result.correct_answers for result in results)
    practice_seconds = sum(result.duration_seconds for result in results)
    grouped: dict[str, list[CompletedResult]] = defaultdict(list)
    for result in results:
        grouped[result.subject_id].append(result)

    strengths = []
    for subject in subjects:
        items = grouped[subject.id]
        attempted = sum(item.scored_questions for item in items)
        correct = sum(item.correct_answers for item in items)
        strengths.append(
            SubjectStrengthResponse(
                subject=subject.name,
                attempted=attempted,
                accuracy=round(correct * 100 / attempted, 1) if attempted else None,
            )
        )

    history = [
        HistoryItemResponse(
            attempt_id=result.id,
            subject=result.subject_name,
            topic=result.topic_name,
            completed_at=result.completed_at,
            correct_answers=result.correct_answers,
            total_questions=result.total_questions,
            scored_questions=result.scored_questions,
            accuracy=round(result.correct_answers * 100 / result.scored_questions, 1)
            if result.scored_questions
            else None,
            duration_seconds=result.duration_seconds,
        )
        for result in results[:12]
    ]
    return ProgressDashboardResponse(
        completed_sets=len(results),
        questions_attempted=total_questions,
        correct_answers=total_correct,
        overall_accuracy=round(total_correct * 100 / total_scored, 1) if total_scored else None,
        practice_seconds=practice_seconds,
        subject_strengths=strengths,
        history=history,
        trend=[
            TrendPointResponse(date=item.completed_at.date().isoformat(), accuracy=item.accuracy)
            for item in reversed([item for item in history if item.accuracy is not None][:7])
        ],
    )
