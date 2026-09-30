"""Publish versioned public study content without replacing student history.

This release bundle contains no users, credentials, attempts or conversations.
Existing reviewed transcriptions and immutable practice questions are preserved.
"""

import json
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision = "20261001_17"
down_revision = "20260930_16"
branch_labels = None
depends_on = None


def publish(connection, bundle: dict) -> None:
    if bundle["version"] != 1:
        raise ValueError("Unsupported public catalog version")
    metadata = sa.MetaData()
    tables = {
        name: sa.Table(name, metadata, autoload_with=connection)
        for name in (
            "subjects",
            "topics",
            "questions",
            "previous_papers",
            "paper_questions",
        )
    }
    subjects, topics, questions, papers, pq = (tables[name] for name in tables)
    subject_ids = set(connection.execute(sa.select(subjects.c.id)).scalars())
    existing_papers = {r["id"]: r for r in connection.execute(sa.select(papers)).mappings()}
    existing_pq = {r["id"]: r for r in connection.execute(sa.select(pq)).mappings()}

    # Check all targets before making any writes. IDs and natural identities must agree.
    for row in bundle["paper_questions"] + bundle["answer_keys"]:
        current = existing_pq.get(row["id"])
        if current is None or (current["paper_id"], current["number"]) != (
            row["paper_id"],
            row["number"],
        ):
            raise ValueError(f"Paper question identity mismatch: {row['id']}")
    for row in bundle["papers"]:
        current = existing_papers.get(row["id"])
        if current is None or any(current[k] != row[k] for k in ("year", "cycle", "source_url")):
            raise ValueError(f"Paper identity mismatch: {row['id']}")
        if current["answer_key_url"] and current["answer_key_url"] != row["answer_key_url"]:
            raise ValueError(f"Existing answer key needs review: {row['id']}")
    for row in bundle["answer_keys"]:
        current = existing_pq[row["id"]]
        if current["is_verified"] and current["correct_index"] != row["correct_index"]:
            raise ValueError(f"Conflicting verified answer: {row['id']}")

    topic_ids = {}
    existing_topics = {
        (r["subject_id"], r["slug"]): r["id"]
        for r in connection.execute(sa.select(topics)).mappings()
    }
    for row in bundle["topics"]:
        if row["subject_id"] not in subject_ids:
            raise ValueError("Missing practice subject")
        natural_key = (row["subject_id"], row["slug"])
        topic_ids[row["id"]] = existing_topics.get(natural_key, row["id"])
        if natural_key not in existing_topics:
            connection.execute(topics.insert().values(**row))
            existing_topics[natural_key] = row["id"]
    existing_question_ids = set(connection.execute(sa.select(questions.c.id)).scalars())
    additions = [
        {**q, "topic_id": topic_ids[q["topic_id"]]}
        for q in bundle["questions"]
        if q["id"] not in existing_question_ids
    ]
    if additions:
        connection.execute(questions.insert(), additions)
    for row in bundle["paper_questions"]:
        if not existing_pq[row["id"]]["transcription"]:
            connection.execute(
                pq.update().where(pq.c.id == row["id"]).values(transcription=row["transcription"])
            )
    for row in bundle["answer_keys"]:
        if not existing_pq[row["id"]]["is_verified"]:
            connection.execute(
                pq.update()
                .where(pq.c.id == row["id"])
                .values(
                    **{
                        key: row[key]
                        for key in ("correct_index", "is_verified", "source_label", "explanation")
                    }
                )
            )
    for row in bundle["papers"]:
        if not existing_papers[row["id"]]["answer_key_url"]:
            connection.execute(
                papers.update()
                .where(papers.c.id == row["id"])
                .values(answer_key_url=row["answer_key_url"])
            )
    if bundle["questions"]:
        # Only known demo seeds: keep the rows and every attempt/answer referencing them.
        connection.execute(
            questions.update()
            .where(questions.c.id.in_(bundle["retire_question_ids"]))
            .values(is_active=False)
        )


def upgrade() -> None:
    path = Path(__file__).resolve().parents[2] / "data" / "release_catalog_20261001.json"
    publish(op.get_bind(), json.loads(path.read_text(encoding="utf-8")))


def downgrade() -> None:
    # Public content may now be referenced by saved attempts. Never delete it on rollback.
    pass
