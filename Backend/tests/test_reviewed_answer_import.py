import asyncio

import pytest

from app.db.session import SessionLocal
from app.models.papers import PaperQuestion, PreviousPaper
from app.models.practice import Subject
from app.services.paper_answers import question_content_fingerprint, stored_answer
from app.services.reviewed_answer_import import import_reviews


async def seed(db):
    subject = Subject(slug="english", code="ENG", name="English", description="Test")
    db.add(subject)
    await db.flush()
    paper = PreviousPaper(
        subject_id=subject.id,
        year=2026,
        cycle="I",
        title="CDS I 2026 English",
        source_url="https://upsc.gov.in/test-paper.pdf",
        source_checksum="exact-source-checksum",
        official_question_count=2,
        academy_tracks=["OTA"],
        questions=[],
    )
    db.add(paper)
    await db.flush()
    for number in [1, 2]:
        paper.questions.append(
            PaperQuestion(
                number=number,
                prompt="Choose the correct verb: She _ to school.",
                options=["go", "goes", "going", "gone"],
                correct_index=0,
                explanation="",
                is_verified=False,
                source_label="Paper scan",
                transcription={
                    "prompt": "Choose the correct verb: She _ to school.",
                    "options": ["go", "goes", "going", "gone"],
                },
            )
        )
    await db.commit()
    payload = {
        "version": 1,
        "year": 2026,
        "cycle": "I",
        "subject_slug": "english",
        "series": "A",
        "source_checksum": paper.source_checksum,
        "questions": [
            {
                "number": q.number,
                "content_fingerprint": question_content_fingerprint(q),
                "correct_index": 1,
                "explanation": "The singular subject she takes the verb goes.",
            }
            for q in paper.questions
        ],
    }
    return paper.id, [q.id for q in paper.questions], payload


def test_manifest_dry_run_then_apply_is_idempotent_and_preserves_official_keys():
    async def scenario():
        async with SessionLocal() as db:
            _, ids, payload = await seed(db)
            dry = await import_reviews(db, payload, apply=False)
            assert dry["ready"] == 2 and dry["saved"] == 0
            assert (await db.get(PaperQuestion, ids[0])).answer_review is None
            q2 = await db.get(PaperQuestion, ids[1])
            q2.is_verified = True
            q2.correct_index = 3
            await db.commit()
            applied = await import_reviews(db, payload, apply=True)
            assert applied["saved"] == 1 and applied["official_preserved"] == 1
            q1 = await db.get(PaperQuestion, ids[0])
            assert stored_answer(q1).index == 1 and q1.is_verified is False
            assert q1.correct_index == 0  # Legacy placeholder is not silently promoted.
            assert stored_answer(q2).index == 3
            again = await import_reviews(db, payload, apply=True)
            assert again["saved"] == 0 and again["existing"] == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("error", ["source", "text", "duplicate", "option"])
def test_invalid_manifest_never_commits_partial_answers(error):
    async def scenario():
        async with SessionLocal() as db:
            _, ids, payload = await seed(db)
            if error == "source":
                payload["source_checksum"] = "different-paper"
            elif error == "text":
                payload["questions"][1]["content_fingerprint"] = "changed-text"
            elif error == "duplicate":
                payload["questions"][1]["number"] = 1
            else:
                payload["questions"][1]["correct_index"] = True
            with pytest.raises(ValueError):
                await import_reviews(db, payload, apply=True)
            await db.rollback()
        async with SessionLocal() as db:
            for qid in ids:
                assert (await db.get(PaperQuestion, qid)).answer_review is None

    asyncio.run(scenario())


def test_manifest_content_hash_is_portable_but_stored_reviews_are_paper_bound():
    q = PaperQuestion(
        paper_id="local-id", number=1, prompt="Test", options=["A", "B"], context=None
    )
    portable = question_content_fingerprint(q)
    from app.services.paper_answers import question_fingerprint

    bound = question_fingerprint(q)
    q.paper_id = "production-id"
    assert question_content_fingerprint(q) == portable
    assert question_fingerprint(q) != bound
