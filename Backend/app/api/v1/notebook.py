from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.auth import User, utc_now
from app.models.practice import Subject
from app.models.revision import RevisionAnswer, RevisionSession
from app.schemas.notebook import SaveRevisionRequest, StartRevisionRequest
from app.services.mistake_notebook import (
    notebook_entries,
    public_revision_question,
    question_snapshots,
    revision_questions,
)

router = APIRouter(prefix="/notebook", tags=["revision"])
CurrentUser = Annotated[User, Depends(get_current_user)]
AsyncDb = Annotated[AsyncSession, Depends(get_db)]


def as_utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


async def subject_filter(db: AsyncSession, query, entries, slug: str | None):
    if not slug:
        return query
    subject_id = await db.scalar(select(Subject.id).where(Subject.slug == slug))
    if not subject_id:
        raise HTTPException(404, "This subject could not be found.")
    return query.where(entries.c.subject_id == subject_id)


def session_payload(session: RevisionSession) -> dict:
    return dict(
        id=session.id,
        status=session.status,
        started_at=as_utc(session.started_at),
        completed_at=as_utc(session.completed_at),
        current_position=session.current_position,
        answers=session.answers,
        questions=[public_revision_question(q) for q in session.questions],
    )


def result_payload(session: RevisionSession) -> dict:
    review = []
    for q in session.questions:
        selected = session.answers.get(q["question_key"])
        review.append(
            dict(
                **public_revision_question(q),
                selected_index=selected,
                correct_index=q["correct_index"],
                explanation=q["explanation"],
                is_correct=selected == q["correct_index"],
            )
        )
    correct = sum(q["is_correct"] for q in review)
    answered = sum(q["selected_index"] is not None for q in review)
    return dict(
        id=session.id,
        completed_at=as_utc(session.completed_at),
        total_questions=len(review),
        correct_answers=correct,
        wrong_answers=answered - correct,
        skipped_questions=len(review) - answered,
        review=review,
    )


async def owned_session(db: AsyncSession, user_id: str, session_id: str) -> RevisionSession:
    session = await db.scalar(
        select(RevisionSession)
        .where(
            RevisionSession.id == session_id,
            RevisionSession.user_id == user_id,
        )
        .with_for_update()
    )
    if not session:
        raise HTTPException(404, "This revision set could not be found.")
    return session


def save_state(session: RevisionSession, payload: SaveRevisionRequest) -> None:
    questions = {q["question_key"]: q for q in session.questions}
    if payload.current_position >= len(questions):
        raise HTTPException(422, "Choose a question in this revision set.")
    answers = {}
    for answer in payload.answers:
        question = questions.get(answer.question_key)
        if not question or answer.question_key in answers:
            raise HTTPException(422, "Each answer must belong to this set and appear only once.")
        if answer.selected_index is not None and answer.selected_index >= len(question["options"]):
            raise HTTPException(422, "Choose one of this question's options.")
        answers[answer.question_key] = answer.selected_index
    session.answers = answers
    session.current_position = payload.current_position


@router.get("")
async def get_notebook(
    user: CurrentUser,
    db: AsyncDb,
    subject: str | None = Query(default=None, max_length=80),
    reason: Literal["all", "wrong", "skipped"] = "all",
    state: Literal["pending", "resolved"] = "pending",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict:
    entries = await notebook_entries(db, user.id)
    base = await subject_filter(db, select(entries), entries, subject)
    counts_source = base.subquery()
    counts = (
        (
            await db.execute(
                select(
                    func.count().label("total"),
                    func.sum(case((counts_source.c.state == "pending", 1), else_=0)).label(
                        "pending"
                    ),
                    func.sum(case((counts_source.c.state == "resolved", 1), else_=0)).label(
                        "resolved"
                    ),
                ).select_from(counts_source)
            )
        )
        .mappings()
        .one()
    )
    query = base.where(entries.c.state == state)
    if reason != "all":
        query = query.where(entries.c.reason == reason)
    revision_query = base.where(entries.c.state == "pending")
    if reason != "all":
        revision_query = revision_query.where(entries.c.reason == reason)
    available = await revision_questions(db, revision_query, entries, 20)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await db.execute(
            query.order_by(
                entries.c.completed_at.desc(),
                entries.c.question_key,
            )
            .offset(offset)
            .limit(limit)
        )
    ).all()
    active = await db.scalar(
        select(RevisionSession)
        .where(
            RevisionSession.user_id == user.id,
            RevisionSession.status == "in_progress",
        )
        .order_by(RevisionSession.started_at.desc())
        .limit(1)
    )
    recent = (
        await db.scalars(
            select(RevisionSession)
            .where(
                RevisionSession.user_id == user.id,
                RevisionSession.status == "completed",
            )
            .order_by(RevisionSession.completed_at.desc(), RevisionSession.id.desc())
            .limit(5)
        )
    ).all()
    return dict(
        counts={key: int(value or 0) for key, value in counts.items()},
        items=await question_snapshots(db, rows),
        total=total,
        has_more=offset + len(rows) < (total or 0),
        active_session=session_payload(active) if active else None,
        revision_available=len(available),  # capped at the maximum short-set size
        recent_sessions=[
            dict(
                id=session.id,
                completed_at=as_utc(session.completed_at),
                total_questions=len(session.questions),
                correct_answers=result_payload(session)["correct_answers"],
            )
            for session in recent
        ],
    )


@router.post("/sessions", status_code=201)
async def start_revision(payload: StartRevisionRequest, user: CurrentUser, db: AsyncDb) -> dict:
    # Lock the owner too: double-clicks/concurrent tabs resume one pending set.
    await db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    active = await db.scalar(
        select(RevisionSession)
        .where(
            RevisionSession.user_id == user.id,
            RevisionSession.status == "in_progress",
        )
        .order_by(RevisionSession.started_at.desc())
        .limit(1)
    )
    if active:
        return session_payload(active)
    entries = await notebook_entries(db, user.id)
    query = await subject_filter(
        db, select(entries).where(entries.c.state == "pending"), entries, payload.subject
    )
    if payload.reason != "all":
        query = query.where(entries.c.reason == payload.reason)
    questions = await revision_questions(db, query, entries, payload.question_count)
    if not questions:
        raise HTTPException(
            409,
            "No questions are ready for a revision set here yet. "
            "You can still review their original papers below.",
        )
    session = RevisionSession(
        user_id=user.id,
        questions=questions[: payload.question_count],
        answers={},
        current_position=0,
    )
    db.add(session)
    await db.commit()
    return session_payload(session)


@router.get("/sessions/{session_id}")
async def get_revision(session_id: str, user: CurrentUser, db: AsyncDb) -> dict:
    return session_payload(await owned_session(db, user.id, session_id))


@router.patch("/sessions/{session_id}")
async def save_revision(
    session_id: str, payload: SaveRevisionRequest, user: CurrentUser, db: AsyncDb
) -> dict:
    session = await owned_session(db, user.id, session_id)
    if session.status != "in_progress":
        raise HTTPException(409, "This revision set has already been finished.")
    save_state(session, payload)
    await db.commit()
    return session_payload(session)


@router.post("/sessions/{session_id}/complete")
async def complete_revision(
    session_id: str, payload: SaveRevisionRequest, user: CurrentUser, db: AsyncDb
) -> dict:
    session = await owned_session(db, user.id, session_id)
    if session.status == "completed":
        return result_payload(session)
    save_state(session, payload)
    session.status = "completed"
    session.completed_at = utc_now()
    for question in session.questions:
        selected = session.answers.get(question["question_key"])
        db.add(
            RevisionAnswer(
                session_id=session.id,
                question_key=question["question_key"],
                selected_index=selected,
                is_correct=selected == question["correct_index"],
            )
        )
    await db.commit()
    return result_payload(session)


@router.get("/sessions/{session_id}/result")
async def get_revision_result(session_id: str, user: CurrentUser, db: AsyncDb) -> dict:
    session = await owned_session(db, user.id, session_id)
    if session.status != "completed":
        raise HTTPException(409, "Finish this set to see your answers.")
    return result_payload(session)
