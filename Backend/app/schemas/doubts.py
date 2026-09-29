from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DoubtImage(BaseModel):
    mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    data: str = Field(min_length=4, max_length=5_592_408)


class AskDoubtRequest(BaseModel):
    question: str = Field(default="", max_length=1500)
    subject: Literal["general-knowledge", "elementary-mathematics", "english"] | None = None
    conversation_id: str | None = Field(default=None, max_length=36)
    image: DoubtImage | None = None
    paper_question_id: str | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def require_question_or_image(self) -> "AskDoubtRequest":
        if not self.image and len(self.question.strip()) < 3:
            raise ValueError("Enter a question or attach a question image")
        return self


class StudyProfileUpdate(BaseModel):
    enabled: bool | None = None
    explanation_style: Literal["step-by-step", "concise", "hints-first"] | None = None


class StudyTopic(BaseModel):
    name: str
    count: int


class StudyProfileResponse(BaseModel):
    enabled: bool
    explanation_style: Literal["step-by-step", "concise", "hints-first"]
    topics: list[StudyTopic]
    total_questions: int
    suggested_questions: list[str]


class DoubtSourceResponse(BaseModel):
    id: str
    title: str
    publisher: str
    chapter: str | None
    page_start: int | None
    page_end: int | None
    source_url: str | None
    excerpt: str
    relevance: float


class AskDoubtResponse(BaseModel):
    conversation_id: str
    answer: str
    confidence: float = Field(ge=0, le=1)
    grounded: bool
    sources: list[DoubtSourceResponse]
    follow_up_questions: list[str]
    pyq_result: dict | None = None
    practice_result: dict | None = None
    answer_kind: Literal["explanation", "pyq", "practice", "clarification", "archive_info"] = (
        "explanation"
    )


class DoubtMessageResponse(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    citations: list[DoubtSourceResponse]
    confidence: float | None
    created_at: datetime
    pyq_result: dict | None = None
    practice_result: dict | None = None


class DoubtConversationResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[DoubtMessageResponse]
