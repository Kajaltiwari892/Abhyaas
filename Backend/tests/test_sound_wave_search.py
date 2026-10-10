import asyncio
from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.db.session import SessionLocal
from app.models.papers import PaperQuestion, PreviousPaper
from app.models.practice import Subject
from app.services.question_bank import classify_topics, resolve_query, search_bank
from app.services.rag import RagService


@pytest.mark.parametrize(
    "name",
    [
        "Sound and Waves",
        "sounds and waves",
        "sound waves",
        "acoustics",
        "sound & waves",
        "physics sound and waves",
        "sound-and-waves",
    ],
)
def test_chapter_names_and_parent_subject(name):
    query = resolve_query(f"Give me all {name} PYQs", None)
    assert query.chapter == "sound-waves" and query.subject == "general-knowledge"
    assert query.all_matches and query.limit == 50
    assert query.focus is None and not query.terms


@pytest.mark.parametrize(
    "prompt",
    [
        "A sound wave has a wavelength of 1.65 m.",
        "Which waves are used in SONAR?",
        "What is an echo?",
        "Which of these statements about ultrasonic waves is correct?",
        "A tuning fork produces vibrations.",
        "Which waves are infrasonic?",
        "What is ultrasound used for?",
        "Which animals hear infrasound?",
    ],
)
def test_sound_subtopics_without_literal_chapter_name(prompt):
    tags = classify_topics({"prompt": prompt}, "general-knowledge")
    assert {"sound-waves", "physics"} <= set(tags)
    assert "sound-waves" not in classify_topics({"prompt": prompt}, "english")


@pytest.mark.parametrize(
    "prompt",
    [
        "S-waves generated during an earthquake create crests and troughs.",
        "Which wavelengths are visible electromagnetic radiation?",
        "The frequency of radiation used in an atomic clock is stable.",
        "Which is a sound economic policy?",
        "Explain ocean waves and tides.",
        "Doppler spectroscopy measures redshift of light waves.",
        "A mass on a spring performs simple harmonic motion.",
    ],
)
def test_unrelated_waves_and_ambiguous_words_are_not_sound(prompt):
    assert "sound-waves" not in classify_topics({"prompt": prompt}, "general-knowledge")


def test_subtopic_and_followups_do_not_leak_old_filters():
    echo = resolve_query("Give me echo PYQs from CDS II 2023", None)
    assert echo.chapter == "sound-waves" and echo.focus == "echoes"
    previous = {"query": vars(echo), "returned": 10, "kind": "pyq"}
    all_sound = resolve_query("Give me all Sound and Waves PYQs", None, previous)
    assert all_sound.focus is None
    next_query = resolve_query("Show next PYQs", None, previous)
    assert next_query.focus == "echoes" and next_query.offset == 10
    changed = resolve_query("now modern history", None, previous)
    assert changed.chapter == "modern-history" and changed.focus is None
    assert resolve_query("Explain why sound cannot travel in a vacuum", None, previous) is None


@pytest.mark.parametrize(
    "topic,focus",
    [
        ("ultrasound", "ultrasound"),
        ("ultrasonic", "ultrasound"),
        ("infrasound", "infrasound"),
        ("infrasonic", "infrasound"),
        ("echoes", "echoes"),
        ("SONAR", "ultrasound"),
        ("Doppler effect", "doppler-effect"),
    ],
)
def test_subtopic_requests_are_narrow_not_the_whole_chapter(topic, focus):
    query = resolve_query(f"Give me {topic} PYQs", None)
    assert query.chapter == "sound-waves" and query.focus == focus


def test_all_matches_pagination_legacy_tags_coverage_and_no_generation():
    async def scenario():
        async with SessionLocal() as db:
            subject = Subject(
                slug="general-knowledge",
                code="GK",
                name="General Knowledge",
                description="",
                position=1,
            )
            paper = PreviousPaper(
                subject=subject,
                year=2023,
                cycle="II",
                title="CDS II 2023 GK",
                exam_date=date(2023, 9, 3),
                official_question_count=120,
                academy_tracks=["OTA"],
                source_url="https://upsc.gov.in/2023.pdf",
            )
            # Previously imported records may have no topic tags at all.
            for number in range(1, 57):
                paper.questions.append(
                    PaperQuestion(
                        number=number,
                        prompt=f"Sound problem {number}",
                        options=["A", "B", "C", "D"],
                        correct_index=0,
                        explanation="",
                        source_label="UPSC",
                        is_verified=False,
                        transcription={
                            "prompt": f"Sound wave problem {number}",
                            "options": ["A", "B", "C", "D"],
                            "source_page": 3,
                            "topics": [],
                        },
                    )
                )
            paper.questions.append(
                PaperQuestion(
                    number=57,
                    prompt="Seismic waves",
                    options=["A", "B", "C", "D"],
                    correct_index=0,
                    explanation="",
                    source_label="UPSC",
                    is_verified=False,
                    transcription={
                        "prompt": "Seismic S-waves in earthquakes",
                        "options": ["A", "B", "C", "D"],
                        "topics": ["earth-interior"],
                    },
                )
            )
            paper.questions.append(
                PaperQuestion(
                    number=58,
                    prompt="Medical ultrasound",
                    options=["A", "B", "C", "D"],
                    correct_index=0,
                    explanation="",
                    source_label="UPSC",
                    is_verified=False,
                    transcription={
                        "prompt": "Ultrasound is used in medical imaging.",
                        "options": ["A", "B", "C", "D"],
                        "source_page": 3,
                        "topics": [],
                    },
                )
            )
            db.add(paper)
            db.add(
                PreviousPaper(
                    subject=subject,
                    year=2022,
                    cycle="I",
                    title="PDF-only paper",
                    official_question_count=120,
                    academy_tracks=["OTA"],
                    source_url="https://upsc.gov.in/2022.pdf",
                )
            )
            await db.commit()
            service = RagService()
            service._generate_json = AsyncMock(side_effect=AssertionError("Never invent PYQs"))
            first = await service.answer(db, "Give me all sound and waves PYQs", None, [])
            result = first.pyq_result
            assert result["total"] == 57 and result["returned"] == 50 and result["has_more"]
            assert result["catalog_questions"] == 240 and result["indexed_questions"] == 58
            assert all(card["source_url"].endswith("#page=3") for card in result["questions"])
            assert all(card["correct_index"] is None for card in result["questions"])
            more = await search_bank(db, resolve_query("Show next PYQs", None, result))
            assert more["returned"] == 7 and not more["has_more"]
            assert not {q["id"] for q in result["questions"]} & {q["id"] for q in more["questions"]}
            physics = await search_bank(db, resolve_query("Give me physics PYQs", None))
            assert physics["total"] == 57
            ultrasound = await search_bank(db, resolve_query("Give me ultrasound PYQs", None))
            assert ultrasound["total"] == ultrasound["returned"] == 1
            assert ultrasound["questions"][0]["number"] == 58
            infrasound = await search_bank(db, resolve_query("Give me infrasound PYQs", None))
            assert infrasound["total"] == 0
            service._generate_json.assert_not_called()

    asyncio.run(scenario())
