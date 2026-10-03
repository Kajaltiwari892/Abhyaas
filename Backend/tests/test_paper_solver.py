import asyncio
import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.db.session import SessionLocal
from app.main import app
from app.models.papers import PaperQuestion, PreviousPaper
from app.models.practice import Subject
from app.services.paper_solver import (
    PaperSolutionError,
    complete_record,
    solution_request,
    solve_paper,
    validate_solutions,
)
from app.services.rag import RagService, RagUnavailableError, get_rag_service


async def seed(db, total=120, imported=120, subject="english", cycle="I"):
    item = Subject(
        slug=subject,
        code=subject[:10],
        name="English" if subject == "english" else "Mathematics",
        description="Test",
    )
    db.add(item)
    await db.flush()
    paper = PreviousPaper(
        subject_id=item.id,
        year=2026,
        cycle=cycle,
        title=f"CDS {cycle} 2026 {item.name}",
        official_question_count=total,
        academy_tracks=["OTA"],
        source_url="https://upsc.gov.in/test-english.pdf",
        is_published=True,
        questions=[],
    )
    db.add(paper)
    await db.flush()
    for number in range(1, imported + 1):
        record = {
            "prompt": f"Choose the correct word for sentence {number}: She _ to school.",
            "options": ["go", "goes", "going", "gone"],
            "directions": "Choose one option.",
            "passage": f"Full passage for question {number}.",
            "hasVisual": False,
            "source_page": 2,
            "text_reviewed": True,
        }
        paper.questions.append(
            PaperQuestion(
                number=number,
                prompt=record["prompt"],
                options=record["options"],
                correct_index=0,
                explanation="",
                is_verified=False,
                source_label="Official paper",
                transcription=record,
            )
        )
    await db.commit()
    return paper


async def generate(prompt, count):
    records = json.loads(prompt.split("\nRECORDS\n", 1)[1])
    assert count == len(records) <= 10
    return {
        "solutions": [
            {
                "number": r["number"],
                "status": "solved",
                "answer_index": 1,
                "explanation": "The singular subject 'she' takes the present-tense verb 'goes'.",
            }
            for r in records
        ]
    }


def request(text="solve 2026 cds 1 full questions of english subject", previous=None, history=None):
    return solution_request(text, None, previous, history or [])


@pytest.mark.parametrize(
    "text",
    [
        "solve 2026 cds 1 full questions of english subject",
        "Give answers for CDS I 2026 English paper",
        "Explain the CDS I 2026 English paper",
    ],
)
def test_exact_paper_request_is_routed_to_solutions(text):
    parsed = request(text)
    assert (parsed["year"], parsed["cycle"], parsed["subject"], parsed["start"]) == (
        2026,
        "I",
        "english",
        1,
    )


@pytest.mark.parametrize(
    "text",
    [
        "Explain volcanoes",
        "Solve 2x + 3 = 11",
        "Generate 50 English questions",
        "Give me CDS 2026 English PYQs",
        "Explain how climate changed since 2020",
    ],
)
def test_other_intents_still_use_their_own_routes(text):
    assert request(text) is None


def test_legacy_summary_followup_recovers_only_immediate_paper_request():
    history = [("user", "Solve CDS I 2026 English paper"), ("assistant", "Paper summary")]
    assert request("i said to give answer", history=history)["year"] == 2026
    reminders = history + [("user", "I said to give answer"), ("assistant", "Please specify")]
    assert request("give answers", history=reminders)["year"] == 2026
    assert (
        request("i said to give answer", history=history + [("user", "Explain volcanoes")]) is None
    )


def test_full_paper_batches_load_exact_records_and_continue_without_repeating():
    async def scenario():
        async with SessionLocal() as db:
            paper = await seed(db)
            ai = AsyncMock(side_effect=generate)
            first = await solve_paper(db, request(), ai)
            assert first["start"] == 1 and first["end"] == 10 and first["next_number"] == 11
            assert first["paper"]["total"] == 120 and first["has_more"]
            sent = json.loads(ai.call_args.args[0].split("\nRECORDS\n")[1])
            assert sent[0]["passage"] == "Full passage for question 1."
            assert sent[0]["options"] == ["go", "goes", "going", "gone"]
            assert sent[0]["correct_index"] is None  # Never leak the legacy placeholder key.
            assert all(q["solution"]["status"] == "ai" for q in first["questions"])
            assert first["questions"][0]["source_url"].endswith("#page=2")
            second = await solve_paper(db, request("Continue solving", first), ai)
            assert [q["number"] for q in second["questions"]] == list(range(11, 21))
            assert all(not q.is_verified and q.correct_index == 0 for q in paper.questions)
            revisit = await solve_paper(db, request("Why is B correct in Q12?", second), ai)
            assert revisit["start"] == revisit["end"] == 12 and revisit["next_number"] == 21
            following = await solve_paper(db, request("continue", revisit), ai)
            assert following["start"] == 21

    asyncio.run(scenario())


def test_missing_details_clarify_and_new_subject_resets_cursor():
    async def scenario():
        async with SessionLocal() as db:
            clarify = await solve_paper(db, request("Solve 2026 English paper"), AsyncMock())
            assert clarify["status"] == "clarification"
            completed = request("CDS II", clarify)
            assert completed["cycle"] == "II" and completed["subject"] == "english"
            state = {"kind": "paper_solution", "request": completed, "next_number": 41}
            switch = request("switch to maths", state)
            assert switch["subject"] == "elementary-mathematics" and switch["start"] == 1
            assert request("Explain volcanoes", state) is None
            new = request("Solve CDS I 2025 GK paper", state)
            assert new["year"] == 2025 and new["subject"] == "general-knowledge"

    asyncio.run(scenario())


def test_absent_paper_or_pdf_only_never_calls_ai_or_invents_questions():
    async def scenario():
        async with SessionLocal() as db:
            ai = AsyncMock(side_effect=AssertionError("Do not generate missing paper questions"))
            assert (await solve_paper(db, request(), ai))["status"] == "unavailable"
            await seed(db, imported=0)
            result = await solve_paper(db, request(), ai)
            assert result["status"] == "unavailable" and not result["questions"]
            assert "not been imported" in result["message"]

    asyncio.run(scenario())


def test_missing_visual_passage_and_rows_are_flagged_not_solved():
    async def scenario():
        async with SessionLocal() as db:
            paper = await seed(db, total=10, imported=3)
            paper.questions[0].transcription = {
                **paper.questions[0].transcription,
                "hasVisual": True,
            }
            paper.questions[1].transcription = {
                **paper.questions[1].transcription,
                "directions": "Read the following passage",
                "passage": None,
            }
            await db.commit()
            ai = AsyncMock(side_effect=generate)
            result = await solve_paper(db, request(), ai)
            assert ai.call_args.args[1] == 1
            assert result["questions"][0]["solution"]["status"] == "needs_source"
            assert result["questions"][1]["solution"]["answer_index"] is None
            assert result["questions"][2]["solution"]["status"] == "ai"
            assert result["questions"][-1]["solution"]["status"] == "needs_source"

    asyncio.run(scenario())


def test_verified_key_is_not_overwritten_by_ai_and_official_only_never_guesses():
    async def scenario():
        async with SessionLocal() as db:
            paper = await seed(db, total=3, imported=3)
            paper.questions[0].is_verified = True
            paper.questions[0].correct_index = 2
            await db.commit()
            result = await solve_paper(db, request(), generate)
            first = result["questions"][0]
            assert first["solution"]["status"] == "key_conflict"
            assert first["solution"]["answer_index"] == 2
            ai = AsyncMock()
            official = await solve_paper(
                db, request("Give official answers for CDS I 2026 English"), ai
            )
            ai.assert_not_called()
            assert official["questions"][0]["solution"]["status"] == "verified"
            assert official["questions"][1]["solution"]["status"] == "key_pending"
            assert paper.questions[1].correct_index == 0 and not paper.questions[1].is_verified

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"number": 2, "status": "solved", "answer_index": 1, "explanation": "Reasoning here"}],
        [{"number": 1, "status": "solved", "answer_index": 9, "explanation": "Reasoning here"}],
        [{"number": 1, "status": "uncertain", "answer_index": 1, "explanation": "Reasoning here"}],
    ],
)
def test_partial_wrong_number_or_invalid_options_are_rejected(rows):
    with pytest.raises(PaperSolutionError):
        validate_solutions({"solutions": rows}, [1])


def test_rag_uses_solver_not_overview_and_does_not_fallback_after_provider_failure():
    async def scenario():
        async with SessionLocal() as db:
            await seed(db, total=2, imported=2)
            service = RagService()
            service.retrieve = AsyncMock(side_effect=AssertionError("No overview retrieval"))
            service._generate_paper_json = AsyncMock(side_effect=generate)
            result = await service.answer(db, "Solve CDS I 2026 English paper", None, [])
            assert (
                result.answer_kind == "paper_solution" and len(result.pyq_result["questions"]) == 2
            )
            service._generate_paper_json = AsyncMock(
                side_effect=RagUnavailableError("Quota reached")
            )
            with pytest.raises(RagUnavailableError, match="Quota reached"):
                await service.answer(db, "Solve CDS I 2026 English paper", None, [])

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "text",
    [
        "Create 50 CDS English questions with answers",
        "Generate similar CDS questions and solutions",
    ],
)
def test_new_practice_with_answers_is_not_mistaken_for_an_actual_paper(text):
    assert request(text) is None


def test_existing_archive_explain_first_stays_on_exact_card_route():
    assert request("Explain the first one", {"kind": "pyq", "questions": []}) is None
    assert request("Explain this PYQ", {"kind": "pyq", "questions": []}) is None


def test_section_context_includes_antonym_instruction_and_original_reader_passage():
    async def scenario():
        async with SessionLocal() as db:
            paper = await seed(db)
            paper.subject = await db.get(Subject, paper.subject_id)
            paper.source_checksum = (
                "448a3c97245b5c9a2b84bf6ccf118aea295726460d96ca3512c8dd90ab294d51"
            )
            antonym = paper.questions[50]
            antonym.transcription = {**antonym.transcription, "directions": None}
            assert "opposite" in complete_record(antonym, paper)["directions"]
            comprehension = paper.questions[115]
            comprehension.transcription = {
                **comprehension.transcription,
                "directions": None,
                "passage": None,
            }
            complete = complete_record(comprehension, paper)
            frontend = (
                Path(__file__).resolve().parents[2]
                / "Frontend"
                / "abhyaas"
                / "app"
                / "papers"
                / "page.tsx"
            ).read_text(encoding="utf-8")
            passage = json.loads(re.search(r'passage: ("(?:[^"\\]|\\.)*")', frontend)[1])
            assert complete["passage"] == passage
            assert complete["text_reviewed"] is False
            assert comprehension.transcription["passage"] is None  # Read-only enrichment.
            paper.source_checksum = "different-booklet"
            assert complete_record(comprehension, paper)["passage"] is None

    asyncio.run(scenario())


def test_last_batch_range_end_and_short_word_questions():
    async def scenario():
        async with SessionLocal() as db:
            paper = await seed(db, total=12, imported=12)
            paper.questions[0].transcription = {
                **paper.questions[0].transcription,
                "prompt": "Naive",
            }
            result = await solve_paper(db, request(), generate)
            assert result["questions"][0]["solution"]["status"] == "ai"
            last = await solve_paper(db, request("Now continue", result), generate)
            assert [q["number"] for q in last["questions"]] == [11, 12]
            assert not last["has_more"]
            invalid = await solve_paper(db, request("Solve CDS I 2026 English Q0"), AsyncMock())
            assert invalid["status"] == "clarification"

    asyncio.run(scenario())


def test_provider_schema_has_room_and_exact_cardinality_for_solution_batch():
    async def scenario():
        def respond(req):
            config = json.loads(req.content)["generationConfig"]
            assert config["maxOutputTokens"] == 12288
            assert config["responseJsonSchema"]["properties"]["solutions"]["minItems"] == 10
            return httpx.Response(
                200, json={"candidates": [{"content": {"parts": [{"text": '{"solutions":[]}'}]}}]}
            )

        service = RagService()
        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        with patch("app.services.rag.httpx.AsyncClient", return_value=client):
            await service._generate_paper_json("Test", 10)

    asyncio.run(scenario())


def test_saved_chat_reopens_and_continues_with_private_server_side_cursor(client):
    async def prepare():
        async with SessionLocal() as db:
            await seed(db, total=12, imported=12)

    asyncio.run(prepare())
    service = RagService()
    service._generate_paper_json = AsyncMock(side_effect=generate)
    app.dependency_overrides[get_rag_service] = lambda: service
    try:
        registered = client.post(
            "/api/v1/auth/register",
            json={"name": "Student", "email": "solver@example.com", "password": "secure123"},
        ).json()
        headers = {"Authorization": f"Bearer {registered['access_token']}"}
        result = client.post(
            "/api/v1/doubts/ask",
            headers=headers,
            json={"question": "Solve CDS I 2026 English paper"},
        )
        assert result.status_code == 200, result.text
        data = result.json()
        assert not data["grounded"] and data["answer_kind"] == "paper_solution"
        cid = data["conversation_id"]
        saved = client.get(f"/api/v1/doubts/conversations/{cid}", headers=headers).json()
        assert saved["messages"][-1]["pyq_result"]["next_number"] == 11
        resumed = client.post(
            "/api/v1/doubts/ask",
            headers=headers,
            json={"conversation_id": cid, "question": "continue"},
        ).json()
        assert resumed["pyq_result"]["start"] == 11 and resumed["pyq_result"]["end"] == 12
        assert not resumed["pyq_result"]["has_more"]
        finished = client.post(
            "/api/v1/doubts/ask",
            headers=headers,
            json={"conversation_id": cid, "question": "continue"},
        ).json()
        assert finished["pyq_result"]["status"] == "complete"
        assert service._generate_paper_json.call_count == 2
        assert client.get(f"/api/v1/doubts/conversations/{cid}").status_code == 401
    finally:
        app.dependency_overrides.pop(get_rag_service, None)
