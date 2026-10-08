from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class StudyPreferencesInput(BaseModel):
    daily_minutes: int = Field(default=120, ge=30, le=180, strict=True)
    start_time: str = Field(default="19:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    subject_slugs: list[str] = Field(min_length=1, max_length=3)
    exam_date: date | None = None

    @field_validator("subject_slugs")
    @classmethod
    def supported_subjects(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values) or not set(values) <= {
            "english",
            "general-knowledge",
            "elementary-mathematics",
        }:
            raise ValueError("Choose English, General Knowledge or Mathematics once each")
        return values


class StudyPreferencesResponse(StudyPreferencesInput):
    configured: bool
    timezone: str = "Asia/Kolkata"


class StudyTaskAction(BaseModel):
    action: Literal["start", "pause", "complete", "defer", "restore"]


class StudyCheckinInput(BaseModel):
    answer: Literal["yes", "not-yet", "dismiss"]
    task_id: str = Field(min_length=36, max_length=36)


class StudyTaskResponse(BaseModel):
    id: str
    plan_date: date
    position: int
    subject_slug: str
    subject_name: str
    topic_slug: str
    topic_name: str
    curriculum_key: str | None = None
    focus_points: list[str] = Field(default_factory=list)
    reason: str
    start_minute: int
    study_minutes: int
    quiz_minutes: int
    question_count: int
    study_elapsed_seconds: int
    study_started_at: datetime | None
    study_done: bool
    deferred: bool
    completed: bool
    quiz_answered: int
    quiz_correct: int
    quiz_remaining: int
    quiz_attempt_id: str | None
    quiz_status: str | None


class StudyPlanResponse(BaseModel):
    id: str
    plan_date: date
    daily_minutes: int
    start_time: str
    completed_tasks: int
    tasks: list[StudyTaskResponse]
    version: int = 2
    checkin_seen: bool = False


class StudyDayResponse(BaseModel):
    plan_date: date
    completed_tasks: int
    total_tasks: int
    deferred_tasks: int


class StudyPlanDashboard(BaseModel):
    preferences: StudyPreferencesResponse
    today: date
    plan: StudyPlanResponse | None
    history: list[StudyDayResponse]
    settings_apply_tomorrow: bool = False
    roadmap_summary: dict | None = None
