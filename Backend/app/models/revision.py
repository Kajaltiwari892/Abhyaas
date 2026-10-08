"""Revision is separate from exam attempts: it never rewrites their scores."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.auth import utc_now
from app.models.practice import new_id


class RevisionSession(Base):
    __tablename__ = "revision_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", index=True)
    # Immutable question/key snapshots, never returned wholesale while a set is active.
    questions: Mapped[list[dict]] = mapped_column(JSON)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    current_position: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RevisionAnswer(Base):
    __tablename__ = "revision_answers"
    __table_args__ = (UniqueConstraint("session_id", "question_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("revision_sessions.id", ondelete="CASCADE"), index=True
    )
    question_key: Mapped[str] = mapped_column(String(180), index=True)
    selected_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean)
