from datetime import date, datetime

from pydantic import BaseModel, Field


class PaperListItemResponse(BaseModel):
    id: str
    year: int
    cycle: str
    title: str
    subject_slug: str
    subject_name: str
    exam_date: date | None
    duration_seconds: int
    total_marks: int
    official_question_count: int
    available_question_count: int
    verified_question_count: int
    scorable_question_count: int = 0
    reviewed_question_count: int = 0
    academy_tracks: list[str]
    source_url: str
    solutions_available: bool


class PaperQuestionResponse(BaseModel):
    id: str
    number: int
    topic: str | None
    prompt: str
    context: str | None
    options: list[str]
    asset_url: str | None
    is_verified: bool
    is_scorable: bool = False
    answer_basis: str = "pending"
    transcription: dict | None = None


class PaperSolutionResponse(PaperQuestionResponse):
    correct_index: int | None
    explanation: str | None
    source_label: str


class PaperDetailResponse(PaperListItemResponse):
    negative_mark_fraction: float
    questions: list[PaperSolutionResponse]


class SavePaperAnswerRequest(BaseModel):
    selected_index: int = Field(ge=0, le=9)
    marked_for_review: bool = False
    elapsed_seconds: int | None = Field(default=None, ge=0, le=21600)


class SavedPaperAnswerResponse(BaseModel):
    question_id: str
    selected_index: int
    marked_for_review: bool
    is_correct: bool | None
    correct_index: int | None


class PaperAttemptResponse(BaseModel):
    id: str
    paper_id: str
    title: str
    started_at: datetime
    duration_seconds: int
    elapsed_seconds: int
    resumed: bool
    answers: list[SavedPaperAnswerResponse]
    questions: list[PaperQuestionResponse]


class PaperAnswerSubmission(BaseModel):
    question_id: str
    selected_index: int = Field(ge=0, le=9)
    marked_for_review: bool = False


class CompletePaperAttemptRequest(BaseModel):
    duration_seconds: int = Field(ge=0, le=21600)
    answers: list[PaperAnswerSubmission] = Field(default_factory=list, max_length=200)


class PaperAnswerReviewResponse(BaseModel):
    question_id: str
    selected_index: int | None
    correct_index: int | None
    is_correct: bool | None
    explanation: str | None
    source_label: str
    answer_basis: str = "pending"


class PaperAttemptSummaryResponse(BaseModel):
    attempt_id: str
    total_questions: int
    answered_questions: int
    scored_questions: int
    official_answers: int = 0
    reviewed_answers: int = 0
    provisional_answers: int = 0
    score_basis: str = "practice"
    unscored_questions: int
    correct_answers: int
    incorrect_answers: int
    unanswered_questions: int
    score: float | None
    max_score: float | None
    accuracy: float | None
    duration_seconds: int
    review: list[PaperAnswerReviewResponse]


class PaperAIExplanationResponse(BaseModel):
    correct_index: int = Field(ge=0, le=3)
    explanation: str
    confidence: str
