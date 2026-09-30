from datetime import datetime

from pydantic import BaseModel, Field


class TopicResponse(BaseModel):
    id: str
    slug: str
    name: str
    question_count: int = 0


class SubjectResponse(BaseModel):
    id: str
    slug: str
    code: str
    name: str
    description: str
    topics: list[TopicResponse]
    question_count: int = 0


class StartAttemptRequest(BaseModel):
    subject_slug: str
    topic_slug: str | None = None
    question_count: int = Field(default=25, ge=1, le=120)
    allow_repeats: bool = False


class PracticeQuestionResponse(BaseModel):
    id: str
    position: int
    subject: str
    topic: str
    prompt: str
    context: str | None
    options: list[str]
    source_label: str = "Practice question"
    provenance: dict | None = None


class SavedAnswerResponse(BaseModel):
    question_id: str
    selected_index: int
    marked_for_review: bool


class AttemptResponse(BaseModel):
    id: str
    subject: str
    subject_slug: str
    topic: str | None
    topic_slug: str | None
    status: str = "in_progress"
    started_at: datetime
    duration_seconds: int = 1800
    elapsed_seconds: int = 0
    current_position: int = 0
    negative_mark_fraction: float = 0
    new_questions: int = 0
    repeated_questions: int = 0
    answers: list[SavedAnswerResponse] = Field(default_factory=list)
    questions: list[PracticeQuestionResponse]


class SaveAnswerRequest(BaseModel):
    selected_index: int = Field(ge=0, le=9)
    marked_for_review: bool = False


class AttemptAnswerInput(SaveAnswerRequest):
    question_id: str


class CompleteAttemptRequest(BaseModel):
    duration_seconds: int = Field(ge=0, le=14400)
    current_position: int | None = Field(default=None, ge=0, le=119)
    answers: list[AttemptAnswerInput] = Field(default_factory=list, max_length=120)


class AnswerReviewResponse(BaseModel):
    question_id: str
    selected_index: int | None
    correct_index: int
    is_correct: bool
    explanation: str
    source_label: str
    position: int
    prompt: str
    context: str | None
    options: list[str]
    topic: str
    provenance: dict | None = None


class AttemptSummaryResponse(BaseModel):
    attempt_id: str
    subject: str
    topic: str | None
    total_questions: int
    answered_questions: int
    correct_answers: int
    accuracy: float
    duration_seconds: int
    score: float
    negative_mark_fraction: float
    review: list[AnswerReviewResponse]


class PracticeHistoryItem(BaseModel):
    id: str
    subject: str
    topic: str | None
    status: str
    started_at: datetime
    completed_at: datetime | None
    total_questions: int
    answered_questions: int
    correct_answers: int | None
    duration_seconds: int
    time_limit_seconds: int


class PracticeHistoryPage(BaseModel):
    items: list[PracticeHistoryItem]
    total: int
    has_more: bool


class PracticeAvailability(BaseModel):
    total: int
    unseen: int
    seen: int


class CatalogQuestionPage(BaseModel):
    questions: list[PracticeQuestionResponse]
    total: int
    has_more: bool


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
