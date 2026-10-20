"""Account-owned daily plans; learning check-ins never alter exam results."""

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.auth import utc_now
from app.models.practice import PracticeAttempt, new_id


class StudyPreference(Base):
    __tablename__ = "study_preferences"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    daily_minutes: Mapped[int] = mapped_column(Integer, default=60)
    start_time: Mapped[str] = mapped_column(String(5), default="19:00")
    subject_slugs: Mapped[list[str]] = mapped_column(JSON)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    plan_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DailyStudyPlan(Base):
    __tablename__ = "daily_study_plans"
    __table_args__ = (UniqueConstraint("user_id", "plan_date", name="uq_study_plan_user_day"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_date: Mapped[date] = mapped_column(Date, index=True)
    daily_minutes: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[str] = mapped_column(String(5))
    version: Mapped[int] = mapped_column(Integer, default=2)
    checkin_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    tasks: Mapped[list["DailyStudyTask"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="DailyStudyTask.position"
    )


class DailyStudyTask(Base):
    __tablename__ = "daily_study_tasks"
    __table_args__ = (UniqueConstraint("plan_id", "subject_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(ForeignKey("daily_study_plans.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    subject_slug: Mapped[str] = mapped_column(String(80))
    subject_name: Mapped[str] = mapped_column(String(120))
    topic_slug: Mapped[str] = mapped_column(String(80))
    topic_name: Mapped[str] = mapped_column(String(120))
    curriculum_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    focus_points: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(String(24), default="rotation")
    start_minute: Mapped[int] = mapped_column(Integer)
    study_minutes: Mapped[int] = mapped_column(Integer)
    quiz_minutes: Mapped[int] = mapped_column(Integer)
    question_count: Mapped[int] = mapped_column(Integer)
    study_elapsed_seconds: Mapped[int] = mapped_column(Integer, default=0)
    study_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    study_done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deferred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quiz_attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("practice_attempts.id", ondelete="SET NULL"), nullable=True
    )
    previous_quiz_answered: Mapped[int] = mapped_column(Integer, default=0)
    previous_quiz_correct: Mapped[int] = mapped_column(Integer, default=0)

    plan: Mapped[DailyStudyPlan] = relationship(back_populates="tasks")
    quiz_attempt: Mapped[PracticeAttempt | None] = relationship()


class DailyQuizPreparation(Base):
    """A private, resumable draft; never a started/scored practice attempt."""

    __tablename__ = "daily_quiz_preparations"

    task_id: Mapped[str] = mapped_column(
        ForeignKey("daily_study_tasks.id", ondelete="CASCADE"), primary_key=True
    )
    bank_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    questions: Mapped[list[dict]] = mapped_column(JSON, default=list)
    # Candidates are durable but must never be exposed or scored before review.
    pending_questions: Mapped[list[dict]] = mapped_column(JSON, default=list, server_default="[]")
    failure_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("practice_attempts.id", ondelete="SET NULL"), nullable=True
    )
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
