from typing import Literal

from pydantic import BaseModel, Field


class StartRevisionRequest(BaseModel):
    subject: str | None = Field(default=None, max_length=80)
    reason: Literal["all", "wrong", "skipped"] = "all"
    question_count: int = Field(default=5, ge=1, le=20)


class RevisionAnswerInput(BaseModel):
    question_key: str = Field(min_length=1, max_length=180)
    selected_index: int | None = Field(default=None, ge=0, le=9)


class SaveRevisionRequest(BaseModel):
    current_position: int = Field(default=0, ge=0, le=19)
    # Full answer state, including nulls for cleared choices. Saves are serialized
    # by the client and the session row is locked server-side.
    answers: list[RevisionAnswerInput] = Field(default_factory=list, max_length=20)
