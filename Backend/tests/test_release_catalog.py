import copy
import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.db.base import Base
from app.models.papers import PaperQuestion, PreviousPaper
from app.models.practice import Question, Subject, Topic

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "release_catalog", ROOT / "alembic/versions/20261001_17_publish_catalog.py"
)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)
BUNDLE = json.loads((ROOT / "data/release_catalog_20261001.json").read_text(encoding="utf-8"))


def seed_before_release(connection):
    subject_ids = sorted({t["subject_id"] for t in BUNDLE["topics"]})
    for i, subject_id in enumerate(subject_ids):
        connection.execute(
            Subject.__table__.insert().values(
                id=subject_id,
                slug=f"subject-{i}",
                code=f"S{i}",
                name=f"Subject {i}",
                description="",
                position=i,
            )
        )
    paper_ids = sorted({q["paper_id"] for q in BUNDLE["paper_questions"]})
    known_papers = {p["id"]: p for p in BUNDLE["papers"]}
    for i, paper_id in enumerate(paper_ids):
        record = known_papers.get(
            paper_id, {"year": 2000 + i, "cycle": "I", "source_url": "https://upsc.gov.in"}
        )
        connection.execute(
            PreviousPaper.__table__.insert().values(
                id=paper_id,
                subject_id=subject_ids[i % 3],
                title=f"Paper {i}",
                year=record["year"],
                exam_date=date(record["year"], 9, 1),
                cycle=record["cycle"],
                source_url=record["source_url"],
                duration_seconds=7200,
                total_marks=100,
                official_question_count=120,
                negative_mark_fraction=1 / 3,
                academy_tracks=["OTA"],
                is_published=True,
            )
        )
    connection.execute(
        PaperQuestion.__table__.insert(),
        [
            dict(
                id=q["id"],
                paper_id=q["paper_id"],
                number=q["number"],
                prompt="Original scan",
                options=["A", "B", "C", "D"],
                correct_index=0,
                explanation="Pending key",
                source_label="UPSC paper",
                is_verified=False,
            )
            for q in BUNDLE["paper_questions"]
        ],
    )
    connection.execute(
        Topic.__table__.insert().values(
            id="demo-topic",
            subject_id=subject_ids[0],
            slug="demo",
            name="Demo",
            position=0,
        )
    )
    connection.execute(
        Question.__table__.insert().values(
            id=BUNDLE["retire_question_ids"][0],
            topic_id="demo-topic",
            prompt="Saved demo question",
            options=["A", "B", "C", "D"],
            correct_index=1,
            explanation="Saved explanation",
            source_label="Original practice",
            difficulty="foundation",
            is_active=True,
        )
    )


def test_public_bundle_shape_and_counts():
    assert set(BUNDLE) == {
        "version",
        "description",
        "topics",
        "questions",
        "paper_questions",
        "answer_keys",
        "papers",
        "retire_question_ids",
    }
    assert len(BUNDLE["questions"]) == 292
    assert len(BUNDLE["paper_questions"]) == 1700
    assert len(BUNDLE["answer_keys"]) == 340
    assert all(q["provenance"]["kind"] == "pyq" for q in BUNDLE["questions"])
    assert all("prov" not in q["provenance"]["answer_key_url"].lower() for q in BUNDLE["questions"])


def test_publish_is_idempotent_preserves_reviewed_text_and_old_questions():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        seed_before_release(connection)
        preserved_id = BUNDLE["paper_questions"][0]["id"]
        connection.execute(
            PaperQuestion.__table__.update()
            .where(PaperQuestion.id == preserved_id)
            .values(transcription={"prompt": "Reviewed production text"})
        )
        migration.publish(connection, BUNDLE)
        migration.publish(connection, BUNDLE)
        assert (
            connection.scalar(
                sa.select(sa.func.count()).select_from(Question).where(Question.is_active.is_(True))
            )
            == 292
        )
        old = (
            connection.execute(
                sa.select(Question.__table__).where(Question.id == BUNDLE["retire_question_ids"][0])
            )
            .mappings()
            .one()
        )
        assert old["prompt"] == "Saved demo question" and old["correct_index"] == 1
        assert not old["is_active"]
        assert connection.scalar(
            sa.select(PaperQuestion.transcription).where(PaperQuestion.id == preserved_id)
        ) == {"prompt": "Reviewed production text"}
        assert (
            connection.scalar(
                sa.select(sa.func.count())
                .select_from(PaperQuestion)
                .where(PaperQuestion.is_verified.is_(True))
            )
            == 340
        )
    engine.dispose()


def test_conflicting_verified_key_fails_before_writes():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        seed_before_release(connection)
        key = BUNDLE["answer_keys"][0]
        connection.execute(
            PaperQuestion.__table__.update()
            .where(PaperQuestion.id == key["id"])
            .values(is_verified=True, correct_index=(key["correct_index"] + 1) % 4)
        )
        with pytest.raises(ValueError, match="Conflicting verified answer"):
            migration.publish(connection, copy.deepcopy(BUNDLE))
        assert connection.scalar(sa.select(sa.func.count()).select_from(Question)) == 1
    engine.dispose()
