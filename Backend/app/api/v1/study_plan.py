from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import DatabaseSession, get_current_user
from app.models.auth import User
from app.schemas.practice import AttemptResponse, StartAttemptRequest
from app.schemas.study_plan import (
    DailyQuizPreparationResponse,
    StudyCheckinInput,
    StudyPlanDashboard,
    StudyPreferencesInput,
    StudyTaskAction,
    StudyTaskResponse,
)
from app.services import study_plan
from app.services.rag import RagService, get_rag_service

router = APIRouter(prefix="/study-plan", tags=["daily study plan"])
CurrentUser = Annotated[User, Depends(get_current_user)]
RagDependency = Annotated[RagService, Depends(get_rag_service)]


@router.post("/tasks/{task_id}/quiz/prepare", response_model=DailyQuizPreparationResponse)
async def prepare_quiz(
    task_id: str, user: CurrentUser, db: DatabaseSession, rag: RagDependency
) -> DailyQuizPreparationResponse:
    from app.services.quiz_preparation import prepare_step

    return await prepare_step(db, user, task_id, rag)


@router.get("/roadmap")
async def roadmap(user: CurrentUser, db: DatabaseSession) -> dict:
    return await study_plan.roadmap(db, user)


@router.post("/checkin", response_model=StudyPlanDashboard)
async def checkin(payload: StudyCheckinInput, user: CurrentUser, db: DatabaseSession):
    await study_plan.checkin(db, user, payload.task_id, payload.answer)
    return await study_plan.dashboard(db, user)


@router.get("/today", response_model=StudyPlanDashboard)
async def today(user: CurrentUser, db: DatabaseSession) -> StudyPlanDashboard:
    return await study_plan.dashboard(db, user)


@router.post("/today", response_model=StudyPlanDashboard)
async def create_today(user: CurrentUser, db: DatabaseSession) -> StudyPlanDashboard:
    await study_plan.ensure_today(db, user)
    return await study_plan.dashboard(db, user)


@router.put("/preferences", response_model=StudyPlanDashboard)
async def preferences(
    payload: StudyPreferencesInput, user: CurrentUser, db: DatabaseSession
) -> StudyPlanDashboard:
    tomorrow = await study_plan.set_preferences(db, user, payload)
    result = await study_plan.dashboard(db, user)
    result.settings_apply_tomorrow = tomorrow
    return result


@router.get("/tasks/{task_id}", response_model=StudyTaskResponse)
async def task(task_id: str, user: CurrentUser, db: DatabaseSession) -> StudyTaskResponse:
    item = await study_plan.owned_task(db, user.id, task_id)
    study_plan.require_today(item)
    return study_plan.task_view(item, item.plan.plan_date)


@router.patch("/tasks/{task_id}", response_model=StudyPlanDashboard)
async def change_task(
    task_id: str, payload: StudyTaskAction, user: CurrentUser, db: DatabaseSession
) -> StudyPlanDashboard:
    await study_plan.change_task(db, user, task_id, payload.action)
    return await study_plan.dashboard(db, user)


@router.post("/tasks/{task_id}/quiz", response_model=AttemptResponse)
async def quiz(
    task_id: str, user: CurrentUser, db: DatabaseSession, rag: RagDependency
) -> AttemptResponse:
    from app.api.v1.practice import start_attempt

    item = await study_plan.owned_task(db, user.id, task_id)
    if item.plan.version >= 2:
        from app.services.daily_quiz import start_daily_quiz

        return await start_daily_quiz(db, user, task_id, rag)
    return await start_attempt(
        StartAttemptRequest(
            subject_slug=item.subject_slug,
            topic_slug=item.topic_slug,
            study_task_id=item.id,
            allow_repeats=True,
        ),
        user,
        db,
    )
