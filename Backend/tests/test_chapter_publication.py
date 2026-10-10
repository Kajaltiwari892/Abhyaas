import copy

import pytest
import sqlalchemy as sa

from app.db.base import Base
from app.models.papers import PaperQuestion, PreviousPaper
from app.models.practice import Subject
from app.services.chapter_publication import publish, validate_bundle
from app.services.question_bank import text_checksum
from scripts.import_question_bank import prepare_record


def bundle_fixture():
    question = {
        "number": 5,
        "page": 3,
        "prompt": "Sonic boom is produced when a source of sound travels at a speed :",
        "options": [
            "greater than the speed of sound.",
            "greater than the speed of light.",
            "lesser than the speed of sound.",
            "equal to the speed of sound.",
        ],
        "hasVisual": False,
        "source_compared": True,
        "review_note": "Test source comparison; not an answer-key review.",
    }
    question["checksum"] = text_checksum(question)
    return {
        "version": 1,
        "chapter": "sound-waves",
        "papers": [
            {
                "year": 2023,
                "cycle": "II",
                "subject_slug": "general-knowledge",
                "source_url": "https://upsc.gov.in/2023.pdf",
                "source_checksum": "a" * 64,
                "questions": [question],
            }
        ],
    }


@pytest.fixture
def chapter_db():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as db:
        db.execute(
            Subject.__table__.insert().values(
                id="gk",
                slug="general-knowledge",
                code="GK",
                name="General Knowledge",
                description="",
            )
        )
        db.execute(
            PreviousPaper.__table__.insert().values(
                id="paper",
                subject_id="gk",
                year=2023,
                cycle="II",
                title="Preserve this title",
                official_question_count=120,
                academy_tracks=["OTA"],
                source_url="https://upsc.gov.in/2023.pdf",
            )
        )
        yield db
    engine.dispose()


def test_dry_run_and_idempotent_public_content_only(chapter_db):
    bundle = bundle_fixture()
    assert publish(chapter_db, bundle, apply=False)["created"] == 1
    assert chapter_db.scalar(sa.select(sa.func.count()).select_from(PaperQuestion)) == 0
    assert publish(chapter_db, bundle)["created"] == 1
    question = chapter_db.execute(sa.select(PaperQuestion.__table__)).mappings().one()
    assert question["transcription"]["topics"] == ["physics", "sound-waves"]
    assert question["transcription"]["sourcePageUrl"].endswith("#page=3")
    assert question["transcription"]["chapter_review"]["checksum"] == text_checksum(
        question["transcription"]
    )
    assert question["transcription"]["text_reviewed"] is True
    assert question["is_verified"] is False and question["answer_review"] is None
    assert publish(chapter_db, bundle) == {"created": 0, "updated": 0, "sources": 0}
    assert chapter_db.scalar(sa.select(PreviousPaper.title)) == "Preserve this title"


def test_existing_question_ids_keys_and_text_are_preserved(chapter_db):
    bundle = bundle_fixture()
    row = bundle["papers"][0]["questions"][0]
    chapter_db.execute(
        PaperQuestion.__table__.insert().values(
            id="existing-question",
            paper_id="paper",
            number=5,
            prompt=row["prompt"],
            options=row["options"],
            correct_index=2,
            is_verified=True,
            explanation="Existing checked explanation",
            source_label="Official key",
            answer_review={"preserve": True},
            transcription={
                "prompt": row["prompt"],
                "options": row["options"],
                "hasVisual": False,
                "topics": [],
                "transcriptionSource": "preserve-source",
            },
        )
    )
    assert publish(chapter_db, bundle)["updated"] == 1
    question = chapter_db.execute(sa.select(PaperQuestion.__table__)).mappings().one()
    assert question["id"] == "existing-question" and question["correct_index"] == 2
    assert question["is_verified"] and question["answer_review"] == {"preserve": True}
    assert question["explanation"] == "Existing checked explanation"
    assert question["transcription"]["transcriptionSource"] == "preserve-source"
    changed = copy.deepcopy(bundle)
    changed_row = changed["papers"][0]["questions"][0]
    changed_row["prompt"] += " Unexpected change"
    changed_row["checksum"] = text_checksum(changed_row)
    with pytest.raises(ValueError, match="Existing question text differs"):
        publish(chapter_db, changed)


@pytest.mark.parametrize(
    "change", ["options", "checksum", "source", "pdf", "review", "answer", "duplicate"]
)
def test_invalid_content_cannot_be_published(chapter_db, change):
    bundle = bundle_fixture()
    paper = bundle["papers"][0]
    row = paper["questions"][0]
    if change == "options":
        row["options"][3] = ""
    elif change == "checksum":
        row["prompt"] += " Unchecked change"
    elif change == "source":
        paper["source_url"] = "https://upsc.gov.in.example.com/fake.pdf"
    elif change == "pdf":
        paper["source_checksum"] = "missing"
    elif change == "review":
        row["source_compared"] = False
    elif change == "answer":
        row["correct_index"] = 0
    else:
        paper["questions"].append(copy.deepcopy(row))
    with pytest.raises(ValueError):
        publish(chapter_db, bundle)
    assert chapter_db.scalar(sa.select(sa.func.count()).select_from(PaperQuestion)) == 0


def test_all_sources_are_checked_before_any_insert(chapter_db):
    bundle = bundle_fixture()
    missing = copy.deepcopy(bundle["papers"][0])
    missing["year"] = 2022
    bundle["papers"].append(missing)
    with pytest.raises(ValueError, match="Source paper missing"):
        publish(chapter_db, bundle)
    assert chapter_db.scalar(sa.select(sa.func.count()).select_from(PaperQuestion)) == 0


def test_seismic_wave_question_cannot_be_labelled_sound():
    bundle = bundle_fixture()
    row = bundle["papers"][0]["questions"][0]
    row["prompt"] = "Seismic S-waves are produced by earthquakes."
    row["checksum"] = text_checksum(row)
    with pytest.raises(ValueError, match="does not match the chapter"):
        validate_bundle(bundle)


def test_legacy_reimport_keeps_new_source_review_only_for_unchanged_text():
    key = "/papers/cds-ii-2025/general-knowledge/page-11.webp#26"
    record = {"prompt": "A sound wave travels at 330 m/s.", "options": ["A", "B", "C", "D"]}
    checksum = text_checksum(record)
    existing = {
        **record,
        "checksum": checksum,
        "text_reviewed": True,
        "review_note": "Checked source page",
        "topics": ["sound-waves", "physics"],
        "subtopics": ["sound-propagation"],
        "chapter_review": {"chapter": "sound-waves", "checksum": checksum},
    }
    unchanged = prepare_record(key, record, "general-knowledge", {}, existing)
    assert unchanged["text_reviewed"] is True
    assert unchanged["chapter_review"] == existing["chapter_review"]
    assert unchanged["subtopics"] == existing["subtopics"]
    changed = prepare_record(
        key, {**record, "prompt": "Different sound wave text"}, "general-knowledge", {}, existing
    )
    assert changed["text_reviewed"] is False and "chapter_review" not in changed
