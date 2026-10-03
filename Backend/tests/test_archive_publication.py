import copy

import pytest
import sqlalchemy as sa

from app.db.base import Base
from app.models.papers import PaperQuestion, PreviousPaper
from app.models.practice import Subject
from app.services.archive_publication import publish, validate_paper
from scripts.transcribe_archive_papers import validate_batch


def paper_fixture():
    url = "https://www.upsc.gov.in/example.pdf"
    return {
        "year": 2023,
        "cycle": "I",
        "subject_slug": "elementary-mathematics",
        "source_url": url,
        "source_checksum": "a" * 64,
        "question_count": 100,
        "questions": [
            {
                "number": n,
                "page": 3,
                "prompt": f"Test-only question {n}",
                "options": ["One", "Two", "Three", "Four"],
                "complete": True,
                "directions": "",
                "passage": "",
                "sectionTitle": "",
                "hasVisual": False,
                "visualDescription": "",
                "text_reviewed": False,
                "source_compared": True,
                "transcriptionSource": "test-model",
                "transcriptionVersion": 1,
                "sourcePageUrl": url + "#page=3",
                "asset_url": "/papers/cds-i-2023/elementary-mathematics/page-3.webp",
            }
            for n in range(1, 101)
        ],
    }


@pytest.fixture
def archive_db():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as db:
        db.execute(
            Subject.__table__.insert().values(
                id="math",
                slug="elementary-mathematics",
                code="MAT",
                name="Mathematics",
                description="",
            )
        )
        db.execute(
            PreviousPaper.__table__.insert().values(
                id="old-paper",
                subject_id="math",
                year=2023,
                cycle="I",
                title="Original title",
                exam_date=None,
                official_question_count=100,
                academy_tracks=["IMA"],
                source_url="https://www.upsc.gov.in/example.pdf",
            )
        )
        yield db
    engine.dispose()


def test_complete_archive_is_answerable_but_not_falsely_graded(archive_db):
    bundle = {"version": 1, "papers": [paper_fixture()]}
    assert publish(archive_db, bundle) == (1, 100)
    assert archive_db.scalar(sa.select(sa.func.count()).select_from(PaperQuestion)) == 100
    assert (
        archive_db.scalar(
            sa.select(sa.func.count())
            .select_from(PaperQuestion)
            .where(PaperQuestion.is_verified.is_(True))
        )
        == 0
    )
    first = (
        archive_db.execute(sa.select(PaperQuestion.__table__).order_by(PaperQuestion.number))
        .mappings()
        .first()
    )
    assert first["transcription"]["text_reviewed"] is False
    assert first["transcription"]["sourcePageUrl"].endswith("#page=3")
    assert archive_db.scalar(sa.select(PreviousPaper.title)) == "Original title"
    assert archive_db.scalar(sa.select(PreviousPaper.exam_date)) is None
    # A later reviewed key must survive re-running publication.
    archive_db.execute(
        PaperQuestion.__table__.update()
        .where(PaperQuestion.id == first["id"])
        .values(is_verified=True, correct_index=2)
    )
    assert publish(archive_db, bundle) == (0, 0)
    assert (
        archive_db.scalar(
            sa.select(PaperQuestion.correct_index).where(PaperQuestion.id == first["id"])
        )
        == 2
    )


def test_partial_papers_do_not_gain_a_solve_button(archive_db):
    paper = paper_fixture()
    paper["questions"].pop()
    with pytest.raises(ValueError, match="complete, ordered"):
        publish(archive_db, {"version": 1, "papers": [paper]})
    assert archive_db.scalar(sa.select(sa.func.count()).select_from(PaperQuestion)) == 0


@pytest.mark.parametrize("change", ["number", "option", "source", "answer", "review", "page"])
def test_publication_rejects_invalid_content_before_insert(archive_db, change):
    paper = paper_fixture()
    row = paper["questions"][-1]
    if change == "number":
        row["number"] = 1
    elif change == "option":
        row["options"][3] = ""
    elif change == "source":
        paper["source_url"] = "https://example.com/fake.pdf"
    elif change == "answer":
        row["correct_index"] = 0
    elif change == "review":
        row["text_reviewed"] = True
    else:
        row["sourcePageUrl"] = "https://example.com/page"
    with pytest.raises(ValueError):
        publish(archive_db, {"version": 1, "papers": [paper]})
    assert archive_db.scalar(sa.select(sa.func.count()).select_from(PaperQuestion)) == 0


def test_existing_content_is_never_replaced(archive_db):
    bundle = {"version": 1, "papers": [paper_fixture()]}
    publish(archive_db, bundle)
    changed = copy.deepcopy(bundle)
    changed["papers"][0]["questions"][0]["prompt"] = "Unexpected replacement"
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        publish(archive_db, changed)
    assert (
        archive_db.scalar(sa.select(PaperQuestion.prompt).where(PaperQuestion.number == 1))
        == "Test-only question 1"
    )


def test_batch_cannot_silently_drop_or_invent_missing_questions():
    rows = paper_fixture()["questions"][:20]
    assert len(validate_batch({"questions": rows}, 1, 20, 24)) == 20
    with pytest.raises(ValueError, match="Missing, duplicate"):
        validate_batch({"questions": rows[:-1]}, 1, 20, 24)
    rows[-1]["complete"] = False
    with pytest.raises(ValueError, match="unreadable or incomplete"):
        validate_batch({"questions": rows}, 1, 20, 24)


def test_duplicate_question_content_is_rejected():
    paper = paper_fixture()
    paper["questions"][1]["prompt"] = paper["questions"][0]["prompt"]
    with pytest.raises(ValueError, match="Duplicate question content"):
        validate_paper(paper)
