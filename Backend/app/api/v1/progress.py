from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.auth import User
from app.models.practice import PracticeAttempt, Subject
from app.schemas.practice import (
    HistoryItemResponse,
    ProgressDashboardResponse,
    SubjectStrengthResponse,
    TrendPointResponse,
)

router = APIRouter(tags=["progress"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


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
    total_questions = sum(attempt.total_questions for attempt in attempts)
    total_correct = sum(attempt.correct_answers or 0 for attempt in attempts)
    practice_seconds = sum(attempt.duration_seconds or 0 for attempt in attempts)
    grouped: dict[str, list[PracticeAttempt]] = defaultdict(list)
    for attempt in attempts:
        grouped[attempt.subject_id].append(attempt)

    strengths = []
    for subject in subjects:
        items = grouped[subject.id]
        attempted = sum(item.total_questions for item in items)
        correct = sum(item.correct_answers or 0 for item in items)
        strengths.append(
            SubjectStrengthResponse(
                subject=subject.name,
                attempted=attempted,
                accuracy=round(correct * 100 / attempted, 1) if attempted else None,
            )
        )

    history = [
        HistoryItemResponse(
            attempt_id=attempt.id,
            subject=attempt.subject.name,
            topic=attempt.topic.name if attempt.topic else None,
            completed_at=attempt.completed_at,
            correct_answers=attempt.correct_answers or 0,
            total_questions=attempt.total_questions,
            accuracy=round((attempt.correct_answers or 0) * 100 / attempt.total_questions, 1),
            duration_seconds=attempt.duration_seconds or 0,
        )
        for attempt in attempts[:12]
        if attempt.completed_at is not None
    ]
    return ProgressDashboardResponse(
        completed_sets=len(attempts),
        questions_attempted=total_questions,
        correct_answers=total_correct,
        overall_accuracy=round(total_correct * 100 / total_questions, 1)
        if total_questions
        else None,
        practice_seconds=practice_seconds,
        subject_strengths=strengths,
        history=history,
        trend=[
            TrendPointResponse(date=item.completed_at.date().isoformat(), accuracy=item.accuracy)
            for item in reversed(history[:7])
        ],
    )
