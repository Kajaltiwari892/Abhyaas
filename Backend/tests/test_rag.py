import asyncio
import json
from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.db.session import SessionLocal
from app.models.papers import PaperQuestion, PreviousPaper
from app.models.practice import Subject
from app.models.rag import KnowledgeChunk, KnowledgeDocument
from app.services.rag import RagService, RagUnavailableError, RetrievedSource


def test_practice_batches_have_room_for_questions_and_model_specific_reasoning():
    async def scenario():
        for model, expected in [
            ("gemini-3.8-flash", {"thinkingLevel": "low"}),
            ("gemini-2.5-flash", {"thinkingBudget": 1024}),
        ]:

            def respond(request, expected_config=expected):
                config = json.loads(request.content)["generationConfig"]
                assert config["maxOutputTokens"] == 8192
                assert config["thinkingConfig"] == expected_config
                return httpx.Response(
                    200,
                    json={
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {"thought": True, "text": "Not the answer"},
                                        {"text": '{"questions":[]}'},
                                    ]
                                }
                            }
                        ]
                    },
                )

            service = RagService()
            service.settings = service.settings.model_copy(update={"gemini_model": model})
            client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
            with patch("app.services.rag.httpx.AsyncClient", return_value=client):
                assert await service._generate_practice_json("Prepare practice") == {
                    "questions": []
                }

    asyncio.run(scenario())


def test_retrieve_falls_back_to_database_when_vector_index_is_unavailable() -> None:
    async def scenario() -> None:
        async with SessionLocal() as db:
            document = KnowledgeDocument(
                title="CDS Geography Notes",
                publisher="Abhyaas Editorial",
                source_url="https://example.com/weather",
                subject="general-knowledge",
                checksum="document-weather",
            )
            document.chunks.append(
                KnowledgeChunk(
                    chunk_index=0,
                    chapter="Weather and climate",
                    content=(
                        "Weather describes short-term atmospheric conditions, while climate "
                        "describes long-term patterns for a region."
                    ),
                    checksum="chunk-weather",
                )
            )
            db.add(document)
            await db.commit()

            service = RagService()
            service.sync_knowledge = AsyncMock(  # type: ignore[method-assign]
                side_effect=RuntimeError("index locked")
            )
            sources = await service.retrieve(
                db,
                "What is the difference between weather and climate?",
                "general-knowledge",
            )

            assert len(sources) == 1
            assert sources[0].id == "S1"
            assert sources[0].title == "CDS Geography Notes"
            assert "short-term" in sources[0].excerpt

    asyncio.run(scenario())


def test_full_practice_set_gets_a_sufficient_output_budget():
    async def scenario():
        def respond(request):
            config = json.loads(request.content)["generationConfig"]
            assert 24000 <= config["maxOutputTokens"] <= 24576
            questions_schema = config["responseJsonSchema"]["properties"]["questions"]
            assert questions_schema["minItems"] == questions_schema["maxItems"] == 50
            assert questions_schema["items"]["properties"]["correct_index"]["maximum"] == 3
            return httpx.Response(
                200, json={"candidates": [{"content": {"parts": [{"text": '{"questions":[]}'}]}}]}
            )

        service = RagService()
        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        with patch("app.services.rag.httpx.AsyncClient", return_value=client):
            await service._generate_practice_json("Create exactly 50 questions")

    asyncio.run(scenario())


def test_not_a_paper_question_does_not_retrieve_paper_catalog():
    async def scenario():
        service = RagService()
        question = "Explain greenhouse effect. This is not a paper question."
        assert await service._retrieve_paper_sources(None, question, None) == []
        assert not service._needs_official_evidence(question)

    asyncio.run(scenario())


def test_unavailable_ordinary_lesson_does_not_return_irrelevant_paper_excerpts():
    async def scenario():
        service = RagService()
        service.retrieve = AsyncMock(
            return_value=[
                RetrievedSource(
                    "S1", "Paper", "UPSC", None, None, None, None, "120 English questions", 0.4
                )
            ]
        )
        service._generate_json = AsyncMock(side_effect=RagUnavailableError("Provider offline"))
        with pytest.raises(RagUnavailableError):
            await service.answer(None, "Explain the greenhouse effect", None, [])

    asyncio.run(scenario())


def test_rate_limited_models_are_not_hammered_by_repair_calls():
    async def scenario():
        calls = []

        def respond(request):
            calls.append(request.url.path)
            return httpx.Response(429, headers={"retry-after": "120"})

        service = RagService()
        for _ in range(2):
            client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
            with (
                patch("app.services.rag.httpx.AsyncClient", return_value=client),
                pytest.raises(RagUnavailableError, match="rate-limited"),
            ):
                await service._generate_practice_json("Create exactly 50 questions")
        assert len(calls) == 3  # one call per model, not repeated for every repair
        assert all(
            deadline > 0 and status == 429 for deadline, status in service._model_cooldowns.values()
        )

    asyncio.run(scenario())


def test_retrieve_uses_previous_paper_catalog_for_year_and_subject_questions() -> None:
    async def scenario() -> None:
        async with SessionLocal() as db:
            subject = Subject(
                slug="english",
                code="ENG",
                name="English",
                description="CDS English",
                position=1,
            )
            paper = PreviousPaper(
                subject=subject,
                year=2026,
                cycle="I",
                title="CDS I 2026 English",
                exam_date=date(2026, 4, 12),
                duration_seconds=7200,
                total_marks=100,
                official_question_count=120,
                academy_tracks=["IMA", "INA", "AFA", "OTA"],
                source_url="https://upsc.gov.in/example-cds-2026-english.pdf",
            )
            paper.questions.append(
                PaperQuestion(
                    number=1,
                    prompt="Choose the word which is nearest in meaning to the given word.",
                    options=["A", "B", "C", "D"],
                    correct_index=0,
                    explanation="Verified from the official answer key.",
                    source_label="Official CDS I 2026 English paper",
                    is_verified=True,
                )
            )
            db.add(paper)
            await db.commit()

            service = RagService()
            sources = await service._retrieve_paper_sources(
                db, "What questions came in the 2026 CDS English paper?", None
            )

            assert len(sources) == 1
            assert sources[0].title == "CDS I 2026 English"
            assert sources[0].publisher == "Union Public Service Commission"
            assert "120 questions" in sources[0].excerpt
            assert "pair of words" in sources[0].excerpt
            assert "Selected question text" in sources[0].excerpt
            assert sources[0].source_url.endswith(".pdf")

    asyncio.run(scenario())


def test_source_fallback_still_answers_when_generation_is_unavailable() -> None:
    async def scenario() -> None:
        retrieved = RetrievedSource(
            id="S1",
            title="Official paper",
            publisher="UPSC",
            chapter="Overview",
            page_start=None,
            page_end=None,
            source_url="https://example.com/paper.pdf",
            excerpt="The paper contains 120 questions and covers vocabulary.",
            relevance=0.99,
        )
        service = RagService()
        service.retrieve = AsyncMock(return_value=[retrieved])  # type: ignore[method-assign]
        service._generate_json = AsyncMock(  # type: ignore[method-assign]
            side_effect=RagUnavailableError("provider offline")
        )

        result = await service.answer(None, "What was in the paper?", None, [])  # type: ignore[arg-type]

        assert "Official paper" in result.answer
        assert "[S1]" in result.answer
        assert result.sources[0].publisher == "UPSC"
        assert result.confidence == 0.72

    asyncio.run(scenario())


def test_generation_reuses_working_model_and_preserves_image_payload() -> None:
    async def scenario() -> None:
        seen: list[str] = []

        def respond(request: httpx.Request) -> httpx.Response:
            seen.append(request.url.path)
            assert b"inline_data" in request.content
            if "configured-unavailable" in request.url.path:
                return httpx.Response(503)
            return httpx.Response(
                200, json={"candidates": [{"content": {"parts": [{"text": '{"answer":"x = 4"}'}]}}]}
            )

        service = RagService()
        service.settings = service.settings.model_copy(
            update={
                "gemini_model": "configured-unavailable",
            }
        )
        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        with patch("app.services.rag.httpx.AsyncClient", return_value=client):
            result = await service._generate_json("Solve it", image_data="test")
            assert result["answer"] == "x = 4"
        next_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        with patch("app.services.rag.httpx.AsyncClient", return_value=next_client):
            await service._generate_json("Solve another", image_data="test")
        assert len(seen) == 3
        assert "configured-unavailable" in seen[0]
        assert "gemini-3.5-flash-lite" in seen[1]
        assert seen[2] == seen[1]

    asyncio.run(scenario())


def test_geography_lesson_recovers_from_unrelated_source_refusal() -> None:
    async def scenario() -> None:
        service = RagService()
        unrelated = RetrievedSource(
            "S1", "Constitution", "Library", None, None, None, None, "Fundamental rights.", 0.5
        )
        service.retrieve = AsyncMock(return_value=[unrelated])
        service._generate_json = AsyncMock(
            side_effect=[
                {
                    "answer": "The provided evidence does not contain the Earth's interior.",
                    "cited_source_ids": [],
                },
                {"answer": "Earth has a crust, mantle and core.", "confidence": 0.6},
            ]
        )
        result = await service.answer(
            None,
            "Explain the geography chapter earth interiror",
            None,
            [],
        )
        assert "mantle" in result.answer
        assert result.sources == []
        assert service._generate_json.await_count == 2
        assert "repeat earlier source-only refusals" in service._generate_json.call_args.args[0]

    asyncio.run(scenario())


def test_official_answer_key_refusal_does_not_invent_an_answer() -> None:
    async def scenario() -> None:
        service = RagService()
        source = RetrievedSource(
            "S1", "Paper", "UPSC", None, None, None, None, "Questions only, no key.", 0.9
        )
        service.retrieve = AsyncMock(return_value=[source])
        service._generate_json = AsyncMock(
            return_value={
                "answer": "The provided evidence does not contain the official answer key.",
                "cited_source_ids": [],
            }
        )
        result = await service.answer(None, "What is the official CDS 2026 answer key?", None, [])
        assert "does not contain" in result.answer
        assert service._generate_json.await_count == 1

    asyncio.run(scenario())
