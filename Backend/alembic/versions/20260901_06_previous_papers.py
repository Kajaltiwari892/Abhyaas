# ruff: noqa: E501
"""Add previous papers, verified questions, and timed paper attempts.

Revision ID: 20260901_06
Revises: 20260827_05
Create Date: 2026-09-01
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "20260901_06"
down_revision: str | None = "20260827_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAMESPACE = uuid.UUID("7207de75-09b3-4b08-bf78-abe86f898c91")


def stable_id(value: str) -> str:
    return str(uuid.uuid5(NAMESPACE, value))


SOURCES = {
    "english": (
        "https://www.upsc.gov.in/sites/default/files/QP_CDSI2024_ENGLISH_22042024.pdf",
        "06f62fab1b6d5248605e69385fb78335408c2af4d242430478f30d2656c707d3",
        120,
        ["IMA", "INA", "AFA", "OTA Men", "OTA Women"],
    ),
    "general-knowledge": (
        "https://www.upsc.gov.in/sites/default/files/QP_CDSI2024_GENERAL-KNOWLEDGE_22042024.pdf",
        "a9a339aef01c1c00b911a86e2321b94d9416516895131f1bedfaa8e6ef041c43",
        120,
        ["IMA", "INA", "AFA", "OTA Men", "OTA Women"],
    ),
    "elementary-mathematics": (
        "https://www.upsc.gov.in/sites/default/files/"
        "QP_CDSI2024_ELEMENTARY-MATHEMATICS_22042024.pdf",
        "78fe1a8a7f36d5ff80780897e8fee3cb3adda52db9ac80a8aeb5c4cb196400ae",
        100,
        ["IMA", "INA", "AFA"],
    ),
}

QUESTIONS = [
    (
        "english",
        "vocabulary",
        16,
        "Walking on eggshells",
        None,
        [
            "Careful not to offend or upset others",
            "Walking with great care",
            "Making a noisy entry",
            "Undertaking an uncomfortable journey",
        ],
        0,
        "To walk on eggshells means to act very carefully so that another person is not offended or upset.",
    ),
    (
        "english",
        "vocabulary",
        17,
        "Feather your own nest",
        None,
        [
            "To make one's lodgings comfortable",
            "To make money for oneself by dishonest means",
            "To look at something with a lot of pleasure",
            "To make something more important than it really is",
        ],
        1,
        "To feather one's own nest means to use a position or opportunity for personal financial gain, often dishonestly.",
    ),
    (
        "english",
        "vocabulary",
        18,
        "Neither fish nor fowl",
        None,
        [
            "Difficult to describe or classify",
            "Neither this nor that",
            "Strict rules and regulations",
            "Feel awkward because of unfamiliarity",
        ],
        0,
        "The idiom describes something that does not belong clearly to any recognized category.",
    ),
    (
        "english",
        "vocabulary",
        19,
        "Elephant in the room",
        None,
        [
            "The important topic",
            "The unavoidable mind-set",
            "The obvious problem that is being avoided",
            "The prized possession in the room",
        ],
        2,
        "An elephant in the room is an obvious and important problem that people deliberately avoid discussing.",
    ),
    (
        "english",
        "vocabulary",
        20,
        "The ship has sailed",
        None,
        [
            "The matter is carried over",
            "The matter is decided",
            "The opportunity has passed",
            "Seeking new opportunities",
        ],
        2,
        "The expression means that it is too late to act because the opportunity has already passed.",
    ),
    (
        "general-knowledge",
        "history",
        6,
        "Which one among the following was not a part of the action programme of the Non-Cooperation Movement?",
        None,
        [
            "The Congress organisation was to reach down to the village and the Mohalla level",
            "Boycott of government affiliated schools and colleges",
            "Taking control of the law and order machinery of the State by the Congress Working Committee",
            "Surrender of titles and honours given by the government",
        ],
        2,
        "The movement called for boycott and surrender of honours, not seizure of the State's law-and-order machinery.",
    ),
    (
        "general-knowledge",
        "general-science",
        9,
        "Which one of the following statements is true for James Webb Space Telescope launched in December 2021?",
        None,
        [
            "It orbits the Sun, about 15 lakh km away from the Earth",
            "It orbits the Earth, about 15 lakh km away",
            "It is stationary in space nearly 10 lakh km away from the Earth",
            "It revolves around the Moon nearly 3.5 lakh km away from the Earth",
        ],
        0,
        "JWST operates in a halo orbit around the Sun-Earth L2 region, roughly 1.5 million kilometres from Earth, while orbiting the Sun with Earth.",
    ),
    (
        "general-knowledge",
        "general-science",
        10,
        "Which of the following particles are subatomic particles?",
        "1. Electron  2. Proton  3. Neutron  4. Muon",
        ["1 and 4 only", "1, 2, 3 and 4", "2 and 3 only", "1, 2 and 3 only"],
        1,
        "Electrons, protons, neutrons and muons are all particles smaller than atoms and are therefore subatomic particles.",
    ),
    (
        "elementary-mathematics",
        "algebra",
        8,
        "If 2 is a zero of p(x) = x³ + 3x² - 6x - a, what is the sum of the squares of the other zeros?",
        None,
        ["10", "17", "21", "37"],
        1,
        "If the other roots are r and s, then r+s=-5 and rs=4. Therefore r²+s²=(r+s)²-2rs=25-8=17.",
    ),
    (
        "elementary-mathematics",
        "trigonometry",
        9,
        "If t = cos 79°, what is cosec 79°(1 - cos 79°) equal to?",
        None,
        ["√((1+t)/(1-t))", "t/√(1-t²)", "√(1-t²)/t", "√((1-t)/(1+t))"],
        3,
        "Using sin²79°=1-t², (1-t)/sin79°=(1-t)/√((1-t)(1+t))=√((1-t)/(1+t)).",
    ),
    (
        "elementary-mathematics",
        "algebra",
        10,
        "Suppose p(x)=x⁴+a₃x³+a₂x²+a₁x+a₀ and q(x)=x⁴+b₃x³+b₂x²+b₁x+b₀. If α, β, γ, δ are zeros of p(x) and α, β, γ, λ are zeros of q(x), what is (p(x)-q(x))/((x-α)(x-β)(x-γ))?",
        None,
        ["-λ + δ", "λ - δ", "λ + δ", "-λ - δ"],
        1,
        "The cubic coefficient difference is a₃-b₃=λ-δ by Vieta's formula, and the remaining common-root factor cancels.",
    ),
    (
        "elementary-mathematics",
        "algebra",
        11,
        "If x cos θ = x² + p has a real solution for every θ where 0 ≤ θ ≤ π/4, which statement is correct?",
        None,
        ["p = 1/8", "p ≤ 1/8", "p ≥ 1/8", "p ≤ 1/4"],
        1,
        "The quadratic has a real root when cos²θ-4p≥0. The minimum cos²θ on the interval is 1/2, so p≤1/8.",
    ),
    (
        "elementary-mathematics",
        "algebra",
        12,
        "What is the difference between the greatest and least values of cos²θ + 3 sin²θ + 2?",
        None,
        ["4", "3", "2", "1"],
        2,
        "The expression is 3+2sin²θ, whose range is from 3 to 5. The difference is 2.",
    ),
    (
        "elementary-mathematics",
        "geometry",
        13,
        "ABC is right-angled at B, with AB=6 cm and BC=8 cm. What is the perimeter of the square inscribed in triangle ABC with maximum area?",
        None,
        ["24/7 cm", "96/7 cm", "24 cm", "32 cm"],
        1,
        "The largest square at the right-angle vertex has side ab/(a+b)=48/14=24/7 cm, so its perimeter is 96/7 cm.",
    ),
    (
        "elementary-mathematics",
        "algebra",
        14,
        "What is the greatest value of k for which 2x² - 4x + k = 0 has real roots?",
        None,
        ["1", "2", "3", "4"],
        1,
        "Real roots require discriminant 16-8k≥0, hence k≤2. The greatest possible value is 2.",
    ),
]


def upgrade() -> None:
    op.create_table(
        "previous_papers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subject_id", sa.String(36), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("cycle", sa.String(4), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("total_marks", sa.Integer(), nullable=False),
        sa.Column("official_question_count", sa.Integer(), nullable=False),
        sa.Column("negative_mark_fraction", sa.Float(), nullable=False),
        sa.Column("academy_tracks", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.String(700), nullable=False),
        sa.Column("answer_key_url", sa.String(700), nullable=True),
        sa.Column("source_checksum", sa.String(64), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("year", "cycle", "subject_id"),
    )
    op.create_index(op.f("ix_previous_papers_subject_id"), "previous_papers", ["subject_id"])
    op.create_index(op.f("ix_previous_papers_year"), "previous_papers", ["year"])
    op.create_index(op.f("ix_previous_papers_cycle"), "previous_papers", ["cycle"])
    op.create_index(op.f("ix_previous_papers_is_published"), "previous_papers", ["is_published"])
    op.create_table(
        "paper_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "paper_id",
            sa.String(36),
            sa.ForeignKey("previous_papers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic_id", sa.String(36), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("correct_index", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("source_label", sa.String(240), nullable=False),
        sa.Column("asset_url", sa.String(700), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("paper_id", "number"),
    )
    op.create_index(op.f("ix_paper_questions_paper_id"), "paper_questions", ["paper_id"])
    op.create_index(op.f("ix_paper_questions_is_verified"), "paper_questions", ["is_verified"])
    op.create_table(
        "paper_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("paper_id", sa.String(36), sa.ForeignKey("previous_papers.id"), nullable=False),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("correct_answers", sa.Integer(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_paper_attempts_paper_id"), "paper_attempts", ["paper_id"])
    op.create_index(op.f("ix_paper_attempts_user_id"), "paper_attempts", ["user_id"])
    op.create_index(op.f("ix_paper_attempts_status"), "paper_attempts", ["status"])
    op.create_table(
        "paper_answers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "attempt_id",
            sa.String(36),
            sa.ForeignKey("paper_attempts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id", sa.String(36), sa.ForeignKey("paper_questions.id"), nullable=False
        ),
        sa.Column("selected_index", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("marked_for_review", sa.Boolean(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("attempt_id", "question_id"),
    )
    op.create_index(op.f("ix_paper_answers_attempt_id"), "paper_answers", ["attempt_id"])

    paper_table = sa.table(
        "previous_papers",
        sa.column("id"),
        sa.column("subject_id"),
        sa.column("year"),
        sa.column("cycle"),
        sa.column("title"),
        sa.column("exam_date"),
        sa.column("duration_seconds"),
        sa.column("total_marks"),
        sa.column("official_question_count"),
        sa.column("negative_mark_fraction"),
        sa.column("academy_tracks", sa.JSON()),
        sa.column("source_url"),
        sa.column("answer_key_url"),
        sa.column("source_checksum"),
        sa.column("is_published"),
        sa.column("created_at"),
    )
    op.bulk_insert(
        paper_table,
        [
            {
                "id": stable_id(f"paper:2024:I:{slug}"),
                "subject_id": stable_id(f"subject:{slug}"),
                "year": 2024,
                "cycle": "I",
                "title": f"CDS I 2024 - {slug.replace('-', ' ').title()}",
                "exam_date": date(2024, 4, 21),
                "duration_seconds": 7200,
                "total_marks": 100,
                "official_question_count": source[2],
                "negative_mark_fraction": 1 / 3,
                "academy_tracks": source[3],
                "source_url": source[0],
                "answer_key_url": None,
                "source_checksum": source[1],
                "is_published": True,
                "created_at": datetime(2026, 9, 1, tzinfo=UTC),
            }
            for slug, source in SOURCES.items()
        ],
    )
    question_table = sa.table(
        "paper_questions",
        sa.column("id"),
        sa.column("paper_id"),
        sa.column("topic_id"),
        sa.column("number"),
        sa.column("prompt"),
        sa.column("context"),
        sa.column("options", sa.JSON()),
        sa.column("correct_index"),
        sa.column("explanation"),
        sa.column("source_label"),
        sa.column("asset_url"),
        sa.column("is_verified"),
    )
    op.bulk_insert(
        question_table,
        [
            {
                "id": stable_id(f"paper-question:2024:I:{subject}:{number}"),
                "paper_id": stable_id(f"paper:2024:I:{subject}"),
                "topic_id": stable_id(f"topic:{subject}:{topic}"),
                "number": number,
                "prompt": prompt,
                "context": context,
                "options": options,
                "correct_index": correct_index,
                "explanation": explanation,
                "source_label": "UPSC CDS I 2024, Test Booklet Series A - independently verified explanation",
                "asset_url": None,
                "is_verified": True,
            }
            for subject, topic, number, prompt, context, options, correct_index, explanation in QUESTIONS
        ],
    )


def downgrade() -> None:
    op.drop_table("paper_answers")
    op.drop_table("paper_attempts")
    op.drop_table("paper_questions")
    op.drop_table("previous_papers")
