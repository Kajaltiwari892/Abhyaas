from datetime import datetime

from pydantic import BaseModel, Field


class TopicResponse(BaseModel):
    id: str
    slug: str
    name: str


class SubjectResponse(BaseModel):
    id: str
    slug: str
    code: str
    name: str
    description: str
    topics: list[TopicResponse]


class StartAttemptRequest(BaseModel):
    subject_slug: str
    topic_slug: str | None = None
    question_count: int = Field(default=10, ge=1, le=20)


class PracticeQuestionResponse(BaseModel):
    id: str
    position: int
    subject: str
    topic: str
    prompt: str
    context: str | None
    options: list[str]


class AttemptResponse(BaseModel):
    id: str
    subject: str
    topic: str | None
    started_at: datetime
    duration_seconds: int = 1800
    questions: list[PracticeQuestionResponse]


class SaveAnswerRequest(BaseModel):
    selected_index: int = Field(ge=0, le=9)
    marked_for_review: bool = False


class SavedAnswerResponse(BaseModel):
    question_id: str
    selected_index: int
    marked_for_review: bool


class CompleteAttemptRequest(BaseModel):
    duration_seconds: int = Field(ge=0, le=14400)


class AnswerReviewResponse(BaseModel):
    question_id: str
    selected_index: int | None
    correct_index: int
    is_correct: bool
    explanation: str
    source_label: str


class AttemptSummaryResponse(BaseModel):
    attempt_id: str
    total_questions: int
    answered_questions: int
    correct_answers: int
    accuracy: float
    duration_seconds: int
    review: list[AnswerReviewResponse]


class SubjectStrengthResponse(BaseModel):
    subject: str
    attempted: int
    accuracy: float | None


class HistoryItemResponse(BaseModel):
    attempt_id: str
    subject: str
    topic: str | None
    completed_at: datetime
    correct_answers: int
    total_questions: int
    scored_questions: int
    accuracy: float | None
    duration_seconds: int


class TrendPointResponse(BaseModel):
    date: str
    accuracy: float


class ProgressDashboardResponse(BaseModel):
    completed_sets: int
    questions_attempted: int
    correct_answers: int
    overall_accuracy: float | None
    practice_seconds: int
    subject_strengths: list[SubjectStrengthResponse]
    history: list[HistoryItemResponse]
    trend: list[TrendPointResponse]
