import copy
import importlib.util
import json
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.db.base import Base
from app.models.papers import PaperQuestion, PreviousPaper
from app.models.practice import Subject
from scripts.discover_official_paper_archive import ArchiveParser, official_pdf

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "official_archive", ROOT / "alembic/versions/20261001_18_official_paper_archive.py"
)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)
BUNDLE = json.loads((ROOT / "data/upsc_paper_archive_20261001.json").read_text())


def test_official_archive_coverage_and_safe_pdf_urls():
    assert len(BUNDLE["papers"]) == 63
    keys = {(r["year"], r["cycle"], r["subject_slug"]) for r in BUNDLE["papers"]}
    assert len(keys) == 63
    for year in range(2017, 2027):
        for cycle in ["I", "II"]:
            for subject in migration.SUBJECTS:
                assert (year, cycle, subject) in keys
    assert all(official_pdf(row["source_url"]) and row["pdf_checked"] for row in BUNDLE["papers"])
    assert not official_pdf("https://upsc.gov.in.example.com/fake.pdf")
    assert not official_pdf("javascript:alert(1)")
    assert not official_pdf("https://example.com/paper.pdf")


def test_parser_handles_general_english_and_ignores_other_exams():
    rows = "".join(
        f'<li>{name}<a href="https://upsc.gov.in/{n}.pdf">(1 MB)</a></li>'
        for n, name in enumerate(["General English", "General Knowledge", "Elementary Mathematics"])
    )
    parser = ArchiveParser("https://upsc.gov.in/examinations/previous-question-papers")
    parser.feed(
        f"<table><caption>Combined Defence Services Examination(I), 2022</caption>"
        f"<tr><td><ul>{rows}</ul></td></tr></table>"
        f"<table><caption>Different Exam 2022</caption>{rows}</table>"
    )
    assert len(parser.papers) == 3
    assert {p["subject_slug"] for p in parser.papers} == set(migration.SUBJECTS)


def test_archive_is_insert_only_idempotent_and_has_no_fake_questions():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as db:
        for slug, (name, _, _) in migration.SUBJECTS.items():
            db.execute(
                Subject.__table__.insert().values(
                    id=slug, slug=slug, code=slug[:3], name=name, description=""
                )
            )
        assert migration.publish(db, BUNDLE) == 63
        first_id = db.scalar(sa.select(PreviousPaper.id).limit(1))
        db.execute(
            PreviousPaper.__table__.update()
            .where(PreviousPaper.id == first_id)
            .values(
                title="Preserve reviewed metadata", answer_key_url="https://upsc.gov.in/key.pdf"
            )
        )
        assert migration.publish(db, BUNDLE) == 0
        assert (
            db.scalar(sa.select(PreviousPaper.title).where(PreviousPaper.id == first_id))
            == "Preserve reviewed metadata"
        )
        assert db.scalar(sa.select(sa.func.count()).select_from(PaperQuestion)) == 0
        assert db.scalar(sa.select(sa.func.count()).select_from(PreviousPaper)) == 63
        assert (
            db.scalar(sa.select(PreviousPaper.exam_date).where(PreviousPaper.id == first_id))
            is None
        )
    engine.dispose()


def test_invalid_archive_fails_before_any_insert():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as db:
        for slug, (name, _, _) in migration.SUBJECTS.items():
            db.execute(
                Subject.__table__.insert().values(
                    id=slug, slug=slug, code=slug[:3], name=name, description=""
                )
            )
        invalid = copy.deepcopy(BUNDLE)
        invalid["papers"][-1]["source_url"] = "https://example.com/unverified.pdf"
        with pytest.raises(ValueError, match="non-official"):
            migration.publish(db, invalid)
        assert db.scalar(sa.select(sa.func.count()).select_from(PreviousPaper)) == 0
    engine.dispose()
