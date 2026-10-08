"""Deterministic plans using saved practice, not an AI call on every visit.

Dates and timetable labels use IST. Completed quizzes count actual saved answers,
not allocated questions. A moved target is never reported as completed.
"""

from datetime import UTC, date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import User
from app.models.practice import PracticeAttempt, Subject, Topic
from app.models.study_plan import DailyStudyPlan, DailyStudyTask, StudyPreference
from app.schemas.practice import StartAttemptRequest
from app.schemas.study_plan import (
    StudyDayResponse,
    StudyPlanDashboard,
    StudyPlanResponse,
    StudyPreferencesInput,
    StudyPreferencesResponse,
    StudyTaskResponse,
)
from app.services.study_curriculum import CURRICULUM, EXAM_DATE, build_roadmap

IST = timezone(timedelta(hours=5, minutes=30))


def now_utc() -> datetime:
    return datetime.now(UTC)


def today_ist() -> date:
    return now_utc().astimezone(IST).date()


def elapsed(task: DailyStudyTask) -> int:
    seconds = task.study_elapsed_seconds or 0
    if task.study_started_at:
        started = task.study_started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        seconds += max(0, int((now_utc() - started).total_seconds()))
    return min(task.study_minutes * 60, seconds)


def task_view(task: DailyStudyTask, day: date) -> StudyTaskResponse:
    quiz = task.quiz_attempt
    current_answered = len(quiz.answers) if quiz else 0
    answered = (task.previous_quiz_answered or 0) + current_answered
    correct = (task.previous_quiz_correct or 0) + (
        sum(a.is_correct for a in quiz.answers) if quiz and quiz.status == "completed" else 0
    )
    quiz_done = task.question_count == 0 or (
        answered >= task.question_count and quiz is not None and quiz.status == "completed"
    )
    return StudyTaskResponse(
        id=task.id,
        plan_date=day,
        position=task.position,
        subject_slug=task.subject_slug,
        subject_name=task.subject_name,
        topic_slug=task.topic_slug,
        topic_name=task.topic_name,
        curriculum_key=task.curriculum_key,
        focus_points=task.focus_points or [],
        reason=task.reason,
        start_minute=task.start_minute,
        study_minutes=task.study_minutes,
        quiz_minutes=task.quiz_minutes,
        question_count=task.question_count,
        study_elapsed_seconds=elapsed(task),
        study_started_at=task.study_started_at,
        study_done=task.study_done_at is not None,
        deferred=task.deferred_at is not None,
        completed=bool(task.study_done_at and quiz_done and not task.deferred_at),
        quiz_answered=min(task.question_count, answered),
        quiz_correct=min(task.question_count, correct),
        quiz_remaining=max(0, task.question_count - answered),
        quiz_attempt_id=task.quiz_attempt_id,
        quiz_status=quiz.status if quiz else None,
    )


async def recent_plans(db: AsyncSession, user_id: str) -> list[DailyStudyPlan]:
    return list(
        (
            await db.scalars(
                select(DailyStudyPlan)
                .where(
                    DailyStudyPlan.user_id == user_id,
                    DailyStudyPlan.plan_date >= today_ist() - timedelta(days=6),
                    DailyStudyPlan.plan_date <= today_ist(),
                )
                .options(
                    selectinload(DailyStudyPlan.tasks)
                    .selectinload(DailyStudyTask.quiz_attempt)
                    .selectinload(PracticeAttempt.answers)
                )
                .order_by(DailyStudyPlan.plan_date.desc())
            )
        ).all()
    )


def default_subjects(user: User) -> list[str]:
    subjects = ["english", "general-knowledge"]
    if user.target_academy in {"ima", "ina", "afa"}:
        subjects.append("elementary-mathematics")
    return subjects


async def dashboard(db: AsyncSession, user: User) -> StudyPlanDashboard:
    pref = await db.get(StudyPreference, user.id)
    plans = await recent_plans(db, user.id)
    current = next((p for p in plans if p.plan_date == today_ist()), None)
    preferences = StudyPreferencesResponse(
        configured=pref is not None,
        daily_minutes=pref.daily_minutes if pref else 120,
        start_time=pref.start_time if pref else "19:00",
        subject_slugs=pref.subject_slugs if pref else default_subjects(user),
        exam_date=pref.exam_date or EXAM_DATE if pref else EXAM_DATE,
    )
    history = []
    for plan in plans:
        tasks = [task_view(t, plan.plan_date) for t in plan.tasks]
        history.append(
            StudyDayResponse(
                plan_date=plan.plan_date,
                completed_tasks=sum(t.completed for t in tasks),
                total_tasks=len(tasks),
                deferred_tasks=sum(t.deferred for t in tasks),
            )
        )
    current_tasks = [task_view(t, current.plan_date) for t in current.tasks] if current else []
    return StudyPlanDashboard(
        today=today_ist(),
        preferences=preferences,
        plan=StudyPlanResponse(
            id=current.id,
            plan_date=current.plan_date,
            daily_minutes=current.daily_minutes,
            start_time=current.start_time,
            completed_tasks=sum(t.completed for t in current_tasks),
            tasks=current_tasks,
            version=current.version,
            checkin_seen=current.checkin_seen_at is not None,
        )
        if current
        else None,
        history=history,
        roadmap_summary={k: v for k, v in (await roadmap(db, user)).items() if k != "days"}
        if pref
        else None,
    )


async def roadmap(db: AsyncSession, user: User) -> dict:
    pref = await db.get(StudyPreference, user.id)
    if not pref:
        raise HTTPException(409, "Choose your daily study time first.")
    plans = list(
        await db.scalars(
            select(DailyStudyPlan)
            .where(
                DailyStudyPlan.user_id == user.id,
                DailyStudyPlan.plan_date <= today_ist(),
                DailyStudyPlan.plan_date >= (pref.plan_start_date or today_ist()),
            )
            .options(
                selectinload(DailyStudyPlan.tasks)
                .selectinload(DailyStudyTask.quiz_attempt)
                .selectinload(PracticeAttempt.answers)
            )
            .order_by(DailyStudyPlan.plan_date)
        )
    )
    done = {
        t.curriculum_key
        for p in plans
        for t in p.tasks
        if t.curriculum_key and task_view(t, p.plan_date).completed
    }
    current = next((p for p in plans if p.plan_date == today_ist() and p.tasks), None)
    reserved = {t.curriculum_key for t in current.tasks if t.curriculum_key} if current else set()
    result = build_roadmap(
        pref.plan_start_date or today_ist(),
        pref.exam_date or EXAM_DATE,
        pref.daily_minutes,
        pref.subject_slugs,
        done | reserved,
        today_ist() + timedelta(days=1) if current else today_ist(),
    )
    # Reserving today's session prevents duplicates tomorrow; it is not completion.
    result["completed_sessions"] = build_roadmap(
        pref.plan_start_date or today_ist(),
        pref.exam_date or EXAM_DATE,
        pref.daily_minutes,
        pref.subject_slugs,
        done,
        today_ist(),
    )["completed_sessions"]
    if result["completed_sessions"] == result["total_sessions"] and done:
        finish = max(
            p.plan_date
            for p in plans
            if any(
                t.curriculum_key in done and not t.curriculum_key.startswith("revision:")
                for t in p.tasks
            )
        )
        result["projected_finish"] = finish
        result["feasible"] = finish <= result["coverage_deadline"]
    past = []
    for p in plans:
        if p.plan_date >= today_ist():
            continue
        for task in p.tasks:
            view = task_view(task, p.plan_date)
            past.append(
                {
                    "date": p.plan_date,
                    "phase": "completed" if view.completed else "unfinished",
                    "subject_slug": task.subject_slug,
                    "subject_name": task.subject_name,
                    "topic_slug": task.topic_slug,
                    "topic_name": task.topic_name,
                    "curriculum_key": task.curriculum_key,
                    "focus_points": task.focus_points or [],
                    "session": 1,
                    "sessions": 1,
                    "study_minutes": task.study_minutes,
                    "quiz_minutes": task.quiz_minutes,
                    "question_count": task.question_count,
                }
            )
    # Today's saved target is stable even if settings or a completed quiz change.
    if current:
        result["days"] = [d for d in result["days"] if d["date"] != today_ist()]
        for task in reversed(current.tasks):
            view = task_view(task, current.plan_date)
            result["days"].insert(
                0,
                {
                    "date": today_ist(),
                    "phase": "completed" if view.completed else task.reason,
                    "subject_slug": task.subject_slug,
                    "subject_name": task.subject_name,
                    "topic_slug": task.topic_slug,
                    "topic_name": task.topic_name,
                    "curriculum_key": task.curriculum_key,
                    "focus_points": task.focus_points or [],
                    "session": 1,
                    "sessions": 1,
                    "study_minutes": task.study_minutes,
                    "quiz_minutes": task.quiz_minutes,
                    "question_count": task.question_count,
                },
            )
    result["days"] = past + result["days"]
    return result


async def make_tasks(
    db: AsyncSession, user: User, plan: DailyStudyPlan, pref: StudyPreference
) -> None:
    result = await roadmap(db, user)
    day = next((d for d in result["days"] if d["date"] == plan.plan_date), None)
    if not day:
        raise HTTPException(
            409, "Your exam date has passed. Choose your next exam date in plan settings."
        )
    subject = await db.scalar(select(Subject).where(Subject.slug == day["subject_slug"]))
    if not subject:
        raise HTTPException(409, "This subject is not ready yet.")
    topic = await db.scalar(
        select(Topic).where(Topic.subject_id == subject.id, Topic.slug == day["topic_slug"])
    )
    if not topic:
        topic = Topic(
            subject_id=subject.id, slug=day["topic_slug"], name=day["topic_name"], position=100
        )
        db.add(topic)
        await db.flush()
    plan.tasks.append(
        DailyStudyTask(
            plan_id=plan.id,
            position=0,
            subject_slug=subject.slug,
            subject_name=subject.name,
            topic_slug=topic.slug,
            topic_name=day["topic_name"],
            curriculum_key=day["curriculum_key"],
            focus_points=day["focus_points"],
            reason=day["phase"],
            start_minute=int(pref.start_time[:2]) * 60 + int(pref.start_time[3:]),
            study_minutes=day["study_minutes"],
            quiz_minutes=day["quiz_minutes"],
            question_count=50,
        )
    )


async def ensure_today(db: AsyncSession, user: User) -> None:
    # Account lock + unique(user, day) make refreshes/two tabs idempotent.
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    pref = await db.get(StudyPreference, user.id)
    if not pref:
        raise HTTPException(409, "Choose your daily study time to make a plan.")
    pref.exam_date = pref.exam_date or EXAM_DATE
    pref.plan_start_date = pref.plan_start_date or today_ist()
    existing = await db.scalar(
        select(DailyStudyPlan)
        .where(DailyStudyPlan.user_id == user.id, DailyStudyPlan.plan_date == today_ist())
        .options(selectinload(DailyStudyPlan.tasks))
    )
    if existing:
        if existing.version < 2 and not any(
            t.study_started_at
            or t.study_done_at
            or t.study_elapsed_seconds
            or t.quiz_attempt_id
            or t.deferred_at
            for t in existing.tasks
        ):
            existing.tasks.clear()
            await db.flush()
            existing.version = 2
            await make_tasks(db, user, existing, pref)
        elif existing.version < 2:
            # Keep all saved study time/attempts. Earlier short quizzes can be resumed;
            # additional full sets bring their target to 50, without erasing history.
            for task in existing.tasks:
                unit = next(
                    (
                        u
                        for u in CURRICULUM
                        if u.subject == task.subject_slug and u.topic == task.topic_slug
                    ),
                    None,
                )
                if unit:
                    task.curriculum_key = f"{unit.key}:1"
                    task.focus_points = list(unit.points)
                task.question_count = max(50, task.question_count)
                task.quiz_minutes = 60 if task.subject_slug == "elementary-mathematics" else 50
            existing.daily_minutes = sum(t.study_minutes + t.quiz_minutes for t in existing.tasks)
            existing.version = 2
        await db.commit()
        return
    plan = DailyStudyPlan(
        user_id=user.id,
        plan_date=today_ist(),
        daily_minutes=pref.daily_minutes,
        start_time=pref.start_time,
        tasks=[],
    )
    db.add(plan)
    await db.flush()
    await make_tasks(db, user, plan, pref)
    await db.commit()


async def set_preferences(db: AsyncSession, user: User, payload: StudyPreferencesInput) -> bool:
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    pref = await db.get(StudyPreference, user.id)
    if not pref:
        pref = StudyPreference(user_id=user.id)
        db.add(pref)
    pref.daily_minutes = payload.daily_minutes
    pref.start_time = payload.start_time
    pref.subject_slugs = payload.subject_slugs
    exam_date = payload.exam_date or pref.exam_date or EXAM_DATE
    if not today_ist() < exam_date <= today_ist() + timedelta(days=365):
        raise HTTPException(422, "Choose a future exam date within the next year.")
    pref.exam_date = exam_date
    pref.plan_start_date = pref.plan_start_date or today_ist()
    pref.updated_at = now_utc()
    current = next((p for p in await recent_plans(db, user.id) if p.plan_date == today_ist()), None)
    started = bool(
        current
        and any(
            t.study_started_at
            or t.study_done_at
            or t.study_elapsed_seconds
            or t.quiz_attempt_id
            or t.deferred_at
            for t in current.tasks
        )
    )
    if current and not started:
        # Only an untouched plan can be replaced; never erase attempts or focus time.
        for task in list(current.tasks):
            await db.delete(task)
        await db.flush()
        current.tasks.clear()
        current.daily_minutes = pref.daily_minutes
        current.start_time = pref.start_time
        current.version = 2
        current.checkin_seen_at = None
        await make_tasks(db, user, current, pref)
    await db.commit()
    if not current:
        await ensure_today(db, user)
    return started


async def owned_task(db: AsyncSession, user_id: str, task_id: str) -> DailyStudyTask:
    task = await db.scalar(
        select(DailyStudyTask)
        .join(DailyStudyPlan)
        .where(DailyStudyTask.id == task_id, DailyStudyPlan.user_id == user_id)
        .execution_options(populate_existing=True)
        .options(
            selectinload(DailyStudyTask.plan),
            selectinload(DailyStudyTask.quiz_attempt).selectinload(PracticeAttempt.answers),
        )
    )
    if not task:
        raise HTTPException(404, "Study target not found")
    return task


def require_today(task: DailyStudyTask) -> None:
    if task.plan.plan_date != today_ist():
        raise HTTPException(409, "A new day has started. Open today's plan to continue.")


async def change_task(db: AsyncSession, user: User, task_id: str, action: str) -> None:
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    task = await owned_task(db, user.id, task_id)
    require_today(task)
    if task_view(task, task.plan.plan_date).completed:
        if action == "complete":
            return
        raise HTTPException(409, "This target is already complete.")
    if action == "restore":
        task.deferred_at = None
    elif action == "defer":
        task.study_elapsed_seconds = elapsed(task)
        task.study_started_at = None
        task.deferred_at = now_utc()
    else:
        if task.deferred_at:
            raise HTTPException(409, "Restore this target before starting it.")
        if action == "start" and not task.study_done_at:
            # One focus timer per account/day; switching pauses the other timer.
            others = (
                await db.scalars(
                    select(DailyStudyTask).where(
                        DailyStudyTask.plan_id == task.plan_id,
                        DailyStudyTask.id != task.id,
                        DailyStudyTask.study_started_at.is_not(None),
                    )
                )
            ).all()
            for other in others:
                other.study_elapsed_seconds = elapsed(other)
                other.study_started_at = None
            if not task.study_started_at:
                task.study_started_at = now_utc()
        elif action in {"pause", "complete"}:
            task.study_elapsed_seconds = elapsed(task)
            task.study_started_at = None
            if action == "complete" and not task.study_done_at:
                task.study_done_at = now_utc()
    await db.commit()


async def prepare_daily_quiz(
    db: AsyncSession, user: User, payload: StartAttemptRequest
) -> DailyStudyTask:
    task = await owned_task(db, user.id, payload.study_task_id)
    if task.plan.version >= 2:
        raise HTTPException(422, "Open the 50-question quiz from today's plan.")
    require_today(task)
    if not task.study_done_at or task.deferred_at:
        raise HTTPException(409, "Mark your study as done before taking this topic quiz.")
    view = task_view(task, task.plan.plan_date)
    if view.completed or not task.question_count:
        raise HTTPException(409, "Today's quiz target is already complete.")
    if payload.subject_slug != task.subject_slug or payload.topic_slug != task.topic_slug:
        raise HTTPException(422, "The quiz must match today's subject and topic.")
    if task.quiz_attempt and task.quiz_attempt.status == "completed":
        task.previous_quiz_answered += len(task.quiz_attempt.answers)
        task.previous_quiz_correct += sum(a.is_correct for a in task.quiz_attempt.answers)
        task.quiz_attempt_id = None
        task.quiz_attempt = None
    payload.question_count = max(1, task.question_count - task.previous_quiz_answered)
    payload.allow_repeats = True
    return task


async def checkin(db: AsyncSession, user: User, task_id: str, answer: str) -> None:
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    task = await owned_task(db, user.id, task_id)
    require_today(task)
    if answer == "yes" and not task.deferred_at and not task.study_done_at:
        task.study_elapsed_seconds = elapsed(task)
        task.study_started_at = None
        task.study_done_at = now_utc()
    task.plan.checkin_seen_at = task.plan.checkin_seen_at or now_utc()
    await db.commit()
