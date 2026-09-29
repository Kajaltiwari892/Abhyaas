"""Add the practice catalog, attempts, answers, and starter content.

Revision ID: 20260827_05
Revises: 20260825_04
Create Date: 2026-08-27
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260827_05"
down_revision: str | None = "20260825_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAMESPACE = uuid.UUID("7207de75-09b3-4b08-bf78-abe86f898c91")


def stable_id(value: str) -> str:
    return str(uuid.uuid5(NAMESPACE, value))


SUBJECTS = [
    ("english", "ENG", "English", "Build accuracy across language rules and comprehension."),
    (
        "general-knowledge",
        "GK",
        "General Knowledge",
        "Connect core subjects with CDS-relevant awareness.",
    ),
    (
        "elementary-mathematics",
        "MAT",
        "Elementary Mathematics",
        "Strengthen concepts and timed problem-solving.",
    ),
]

TOPICS = {
    "english": ["Grammar", "Vocabulary", "Comprehension", "Error spotting"],
    "general-knowledge": ["History", "Geography", "Polity", "Economics", "General Science"],
    "elementary-mathematics": ["Arithmetic", "Algebra", "Geometry", "Trigonometry", "Mensuration"],
}

QUESTIONS = [
    (
        "english",
        "Grammar",
        "Choose the sentence with correct subject-verb agreement.",
        None,
        [
            "Each of the cadets are ready.",
            "Each of the cadets is ready.",
            "Each of the cadet are ready.",
            "Each cadets is ready.",
        ],
        1,
        "The subject 'each' is singular, so it takes the singular verb 'is'.",
    ),
    (
        "english",
        "Vocabulary",
        "Choose the word closest in meaning to 'resolute'.",
        None,
        ["Uncertain", "Determined", "Careless", "Silent"],
        1,
        "Resolute means admirably purposeful or determined.",
    ),
    (
        "english",
        "Error spotting",
        "Identify the part containing an error.",
        "Neither of the officers / were willing to accept / responsibility for the delay / "
        "No error",
        ["Part A", "Part B", "Part C", "No error"],
        1,
        "'Neither' is singular here, so 'were' should be 'was'.",
    ),
    (
        "english",
        "Grammar",
        "Select the correctly punctuated sentence.",
        None,
        [
            "However the unit continued its advance.",
            "However, the unit continued its advance.",
            "However the unit, continued its advance.",
            "However; the unit, continued its advance.",
        ],
        1,
        "An introductory conjunctive adverb is followed by a comma in this construction.",
    ),
    (
        "english",
        "Comprehension",
        "What is the central idea of the sentence?",
        "Discipline converts repeated small actions into dependable performance under pressure.",
        [
            "Pressure should always be avoided.",
            "Reliable performance grows from consistent disciplined action.",
            "Only large actions create improvement.",
            "Performance is unrelated to habits.",
        ],
        1,
        "The sentence links repeated disciplined actions with reliable performance.",
    ),
    (
        "general-knowledge",
        "Polity",
        "Fundamental Rights are contained in which Part of the Constitution of India?",
        None,
        ["Part II", "Part III", "Part IV", "Part V"],
        1,
        "Fundamental Rights are provided in Part III of the Constitution.",
    ),
    (
        "general-knowledge",
        "History",
        "The Battle of Plassey was fought in which year?",
        None,
        ["1757", "1761", "1764", "1773"],
        0,
        "The Battle of Plassey was fought in 1757.",
    ),
    (
        "general-knowledge",
        "Geography",
        "Which latitude passes through India?",
        None,
        ["Equator", "Tropic of Cancer", "Tropic of Capricorn", "Arctic Circle"],
        1,
        "The Tropic of Cancer passes through India.",
    ),
    (
        "general-knowledge",
        "General Science",
        "What is the SI unit of electric current?",
        None,
        ["Volt", "Ohm", "Ampere", "Watt"],
        2,
        "The ampere is the SI base unit of electric current.",
    ),
    (
        "general-knowledge",
        "Economics",
        "Inflation generally refers to what?",
        None,
        [
            "A sustained rise in the general price level",
            "A fall in total population",
            "An increase in rainfall",
            "A reduction in literacy",
        ],
        0,
        "Inflation is a sustained increase in the general price level of goods and services.",
    ),
    (
        "elementary-mathematics",
        "Arithmetic",
        "What is 25% of 240?",
        None,
        ["40", "50", "60", "80"],
        2,
        "25% is one-fourth, and one-fourth of 240 is 60.",
    ),
    (
        "elementary-mathematics",
        "Algebra",
        "If 3x + 5 = 20, what is x?",
        None,
        ["3", "5", "8", "15"],
        1,
        "Subtract 5 to get 3x = 15, then divide by 3: x = 5.",
    ),
    (
        "elementary-mathematics",
        "Geometry",
        "The sum of the interior angles of a triangle is:",
        None,
        ["90°", "180°", "270°", "360°"],
        1,
        "The interior angles of every triangle sum to 180 degrees.",
    ),
    (
        "elementary-mathematics",
        "Trigonometry",
        "What is sin 30°?",
        None,
        ["0", "1/2", "√3/2", "1"],
        1,
        "The standard trigonometric value of sin 30° is 1/2.",
    ),
    (
        "elementary-mathematics",
        "Mensuration",
        "What is the area of a circle of radius 7 units? Use π = 22/7.",
        None,
        ["44 square units", "77 square units", "154 square units", "308 square units"],
        2,
        "Area = πr² = (22/7) × 7 × 7 = 154 square units.",
    ),
]


def upgrade() -> None:
    op.create_table(
        "subjects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("code", sa.String(12), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_subjects_slug"), "subjects", ["slug"], unique=True)
    op.create_table(
        "topics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "subject_id",
            sa.String(36),
            sa.ForeignKey("subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("subject_id", "slug"),
    )
    op.create_index(op.f("ix_topics_slug"), "topics", ["slug"])
    op.create_table(
        "questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "topic_id",
            sa.String(36),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("correct_index", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("source_label", sa.String(180), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_index(op.f("ix_questions_topic_id"), "questions", ["topic_id"])
    op.create_index(op.f("ix_questions_is_active"), "questions", ["is_active"])
    op.create_table(
        "practice_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("subject_id", sa.String(36), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("topic_id", sa.String(36), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("correct_answers", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_practice_attempts_user_id"), "practice_attempts", ["user_id"])
    op.create_index(op.f("ix_practice_attempts_subject_id"), "practice_attempts", ["subject_id"])
    op.create_index(op.f("ix_practice_attempts_status"), "practice_attempts", ["status"])
    op.create_table(
        "attempt_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "attempt_id",
            sa.String(36),
            sa.ForeignKey("practice_attempts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("attempt_id", "question_id"),
    )
    op.create_index(op.f("ix_attempt_questions_attempt_id"), "attempt_questions", ["attempt_id"])
    op.create_table(
        "practice_answers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "attempt_id",
            sa.String(36),
            sa.ForeignKey("practice_attempts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("selected_index", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("marked_for_review", sa.Boolean(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("attempt_id", "question_id"),
    )
    op.create_index(op.f("ix_practice_answers_attempt_id"), "practice_answers", ["attempt_id"])

    subject_table = sa.table(
        "subjects",
        sa.column("id"),
        sa.column("slug"),
        sa.column("code"),
        sa.column("name"),
        sa.column("description"),
        sa.column("position"),
    )
    topic_table = sa.table(
        "topics",
        sa.column("id"),
        sa.column("subject_id"),
        sa.column("slug"),
        sa.column("name"),
        sa.column("position"),
    )
    question_table = sa.table(
        "questions",
        sa.column("id"),
        sa.column("topic_id"),
        sa.column("prompt"),
        sa.column("context"),
        sa.column("options", sa.JSON()),
        sa.column("correct_index"),
        sa.column("explanation"),
        sa.column("source_label"),
        sa.column("difficulty"),
        sa.column("is_active"),
    )
    op.bulk_insert(
        subject_table,
        [
            {
                "id": stable_id(f"subject:{slug}"),
                "slug": slug,
                "code": code,
                "name": name,
                "description": description,
                "position": position,
            }
            for position, (slug, code, name, description) in enumerate(SUBJECTS)
        ],
    )
    topic_rows = []
    for subject_slug, names in TOPICS.items():
        for position, name in enumerate(names):
            slug = name.lower().replace(" ", "-")
            topic_rows.append(
                {
                    "id": stable_id(f"topic:{subject_slug}:{slug}"),
                    "subject_id": stable_id(f"subject:{subject_slug}"),
                    "slug": slug,
                    "name": name,
                    "position": position,
                }
            )
    op.bulk_insert(topic_table, topic_rows)
    op.bulk_insert(
        question_table,
        [
            {
                "id": stable_id(f"question:{index}"),
                "topic_id": stable_id(f"topic:{subject_slug}:{topic.lower().replace(' ', '-')}"),
                "prompt": prompt,
                "context": context,
                "options": options,
                "correct_index": correct_index,
                "explanation": explanation,
                "source_label": "Original CDS-style practice",
                "difficulty": "foundation",
                "is_active": True,
            }
            for index, (
                subject_slug,
                topic,
                prompt,
                context,
                options,
                correct_index,
                explanation,
            ) in enumerate(QUESTIONS)
        ],
    )


def downgrade() -> None:
    op.drop_table("practice_answers")
    op.drop_table("attempt_questions")
    op.drop_table("practice_attempts")
    op.drop_table("questions")
    op.drop_table("topics")
    op.drop_table("subjects")
