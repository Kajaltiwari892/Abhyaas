import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.auth import utc_now
from app.models.practice import Subject, Topic


def new_id() -> str:
    return str(uuid.uuid4())


class PreviousPaper(Base):
    __tablename__ = "previous_papers"
    __table_args__ = (UniqueConstraint("year", "cycle", "subject_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    cycle: Mapped[str] = mapped_column(String(4), index=True)
    title: Mapped[str] = mapped_column(String(180))
    # Older official PDF listings identify year/cycle but do not give an exam date.
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=7200)
    total_marks: Mapped[int] = mapped_column(Integer, default=100)
    official_question_count: Mapped[int] = mapped_column(Integer)
    negative_mark_fraction: Mapped[float] = mapped_column(Float, default=1 / 3)
    academy_tracks: Mapped[list[str]] = mapped_column(JSON)
    source_url: Mapped[str] = mapped_column(String(700))
    answer_key_url: Mapped[str | None] = mapped_column(String(700), nullable=True)
    source_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    subject: Mapped[Subject] = relationship()
    questions: Mapped[list["PaperQuestion"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", order_by="PaperQuestion.number"
    )


class PaperQuestion(Base):
    __tablename__ = "paper_questions"
    __table_args__ = (UniqueConstraint("paper_id", "number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    paper_id: Mapped[str] = mapped_column(
        ForeignKey("previous_papers.id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    number: Mapped[int] = mapped_column(Integer)
    prompt: Mapped[str] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[list[str]] = mapped_column(JSON)
    correct_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text)
    source_label: Mapped[str] = mapped_column(String(240))
    asset_url: Mapped[str | None] = mapped_column(String(700), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Full, source-linked question text. Separate from answer-key verification.
    transcription: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Independently checked practice answers are not official UPSC keys.
    answer_review: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    paper: Mapped[PreviousPaper] = relationship(back_populates="questions")
    topic: Mapped[Topic | None] = relationship()


class PaperAttempt(Base):
    __tablename__ = "paper_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    paper_id: Mapped[str] = mapped_column(ForeignKey("previous_papers.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", index=True)
    total_questions: Mapped[int] = mapped_column(Integer)
    scored_questions: Mapped[int] = mapped_column(Integer, default=0)
    correct_answers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    paper: Mapped[PreviousPaper] = relationship()
    answers: Mapped[list["PaperAnswer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class PaperAnswer(Base):
    __tablename__ = "paper_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("paper_attempts.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[str] = mapped_column(ForeignKey("paper_questions.id"))
    selected_index: Mapped[int] = mapped_column(Integer)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    attempt: Mapped[PaperAttempt] = relationship(back_populates="answers")
    question: Mapped[PaperQuestion] = relationship()
