"""Publish versioned original practice without touching student work or PYQs."""

import uuid

import sqlalchemy as sa

from app.services.practice_sets import PracticeQuestion
from app.services.study_curriculum import find_unit

NAMESPACE = uuid.UUID("29dc1b80-e0c4-42df-b741-03649fcfb58d")


def validate_bundle(bundle: dict) -> list[dict]:
    unit = find_unit(bundle.get("curriculum_key"))
    if (
        unit is None
        or bundle.get("curriculum_key") != unit.key
        or bundle.get("subject_slug") != unit.subject
        or bundle.get("topic_slug") != unit.topic
        or not isinstance(bundle.get("version"), str)
    ):
        raise ValueError("Invalid lesson bank identity")
    if not isinstance(bundle.get("questions"), list) or len(bundle["questions"]) < 50:
        raise ValueError("A ready lesson bank needs at least 50 checked questions")
    ids, prompts, validated = set(), set(), []
    for item in bundle["questions"]:
        question = PracticeQuestion.model_validate({**item, "topic_slug": unit.topic})
        identity = item.get("id")
        prompt = " ".join(question.prompt.casefold().split())
        if (
            not isinstance(identity, str)
            or not identity.startswith(bundle["version"] + "-")
            or identity in ids
            or prompt in prompts
            or any(k in item for k in ("source_url", "paper_question_id", "answer_verified"))
        ):
            raise ValueError("Invalid/duplicate original practice question")
        ids.add(identity)
        prompts.add(prompt)
        validated.append({"id": identity, **question.model_dump()})
    return validated


def publish(connection, bundle: dict) -> int:
    items = validate_bundle(bundle)
    metadata = sa.MetaData()
    subjects = sa.Table("subjects", metadata, autoload_with=connection)
    topics = sa.Table("topics", metadata, autoload_with=connection)
    questions = sa.Table("questions", metadata, autoload_with=connection)
    topic_id = connection.scalar(
        sa.select(topics.c.id)
        .join(subjects)
        .where(topics.c.slug == bundle["topic_slug"], subjects.c.slug == bundle["subject_slug"])
    )
    if topic_id is None:
        raise ValueError("Lesson topic must exist before publishing its bank")
    entries = []
    for item in items:
        qid = str(uuid.uuid5(NAMESPACE, item["id"]))
        entries.append(
            {
                "id": qid,
                "topic_id": topic_id,
                "owner_user_id": None,
                "prompt": item["prompt"],
                "context": None,
                "options": item["options"],
                "correct_index": item["correct_index"],
                "explanation": item["explanation"],
                "difficulty": "cds",
                "source_label": "Original CDS-style practice",
                "is_active": True,
                "provenance": {
                    "kind": "curated",
                    "curriculum_key": bundle["curriculum_key"],
                    "bank_version": bundle["version"],
                    "review_status": "content_checked",
                    "answer_verified": False,
                },
            }
        )
    existing = {
        row.id: row
        for row in connection.execute(
            sa.select(questions).where(questions.c.id.in_([q["id"] for q in entries]))
        ).mappings()
    }
    new = []
    for entry in entries:
        current = existing.get(entry["id"])
        if current and any(current[key] != value for key, value in entry.items()):
            raise ValueError("Published content changed; create a new bank version")
        if not current:
            new.append(entry)
    if new:
        connection.execute(questions.insert(), new)
    return len(new)
