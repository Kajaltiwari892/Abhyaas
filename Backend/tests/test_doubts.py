import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.rag import RagAnswer, RagUnavailableError, RetrievedSource, get_rag_service


class FakeRagService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def answer(
        self,
        _db: object,
        question: str,
        subject: str | None,
        history: list[tuple[str, str]],
        *,
        personalization: str = "",
        image_data: str | None = None,
        pyq_context: dict | None = None,
        practice_context: dict | None = None,
        explaining_paper_question: bool = False,
    ) -> RagAnswer:
        self.calls.append({"question": question, "subject": subject, "history": history,
                           "personalization": personalization, "image_data": image_data})
        return RagAnswer(
            answer=(
                "Weather is the atmosphere at a particular time; "
                "climate is its long-term pattern [S1]."
            ),
            confidence=0.93,
            sources=[
                RetrievedSource(
                    id="S1",
                    title="Weather",
                    publisher="World Meteorological Organization",
                    chapter="Weather and climate",
                    page_start=None,
                    page_end=None,
                    source_url="https://wmo.int/themes/weather",
                    excerpt=(
                        "Weather is short-term, while climate describes longer-term conditions."
                    ),
                    relevance=0.91,
                )
            ],
            follow_up_questions=["Why are 30-year climate normals used?"],
        )

    async def read_question_image(self, _image_data: str) -> str:
        return "Solve the equation 2x + 3 = 11."


@pytest.fixture
def fake_rag() -> FakeRagService:
    service = FakeRagService()
    app.dependency_overrides[get_rag_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_rag_service, None)


def register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Doubt Student", "email": email, "password": "secure123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_doubt_solver_requires_authentication(client: TestClient, fake_rag: FakeRagService) -> None:
    response = client.post("/api/v1/doubts/ask", json={"question": "What is weather?"})
    assert response.status_code == 401
    assert fake_rag.calls == []


def test_doubt_solver_saves_grounded_conversation(
    client: TestClient, fake_rag: FakeRagService
) -> None:
    headers = register(client, "doubt@example.com")
    response = client.post(
        "/api/v1/doubts/ask",
        headers=headers,
        json={"question": "  What   is the difference between weather and climate?  ",
              "subject": "general-knowledge"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["grounded"] is True
    assert result["confidence"] == 0.93
    assert result["sources"][0]["id"] == "S1"
    assert fake_rag.calls[0]["question"] == "What is the difference between weather and climate?"
    assert fake_rag.calls[0]["subject"] == "general-knowledge"

    history = client.get(
        f"/api/v1/doubts/conversations/{result['conversation_id']}", headers=headers
    )
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["citations"][0]["publisher"] == "World Meteorological Organization"

    follow_up = client.post(
        "/api/v1/doubts/ask",
        headers=headers,
        json={
            "question": "Why does that matter?",
            "conversation_id": result["conversation_id"],
        },
    )
    assert follow_up.status_code == 200
    assert follow_up.json()["conversation_id"] == result["conversation_id"]
    assert [role for role, _content in fake_rag.calls[1]["history"]] == ["user", "assistant"]


def test_conversation_is_private_to_its_owner(
    client: TestClient, fake_rag: FakeRagService
) -> None:
    owner = register(client, "owner@example.com")
    created = client.post(
        "/api/v1/doubts/ask", headers=owner, json={"question": "What is climate?"}
    )
    conversation_id = created.json()["conversation_id"]
    other_user = register(client, "other@example.com")

    read = client.get(
        f"/api/v1/doubts/conversations/{conversation_id}", headers=other_user
    )
    continue_thread = client.post(
        "/api/v1/doubts/ask",
        headers=other_user,
        json={"question": "Tell me more", "conversation_id": conversation_id},
    )
    assert read.status_code == 404
    assert continue_thread.status_code == 404


def test_image_question_uses_vision_and_saves_only_recognized_text(
    client: TestClient, fake_rag: FakeRagService,
) -> None:
    headers = register(client, "image@example.com")
    buffer = io.BytesIO()
    Image.new("RGB", (200, 80), "white").save(buffer, format="PNG")
    data = base64.b64encode(buffer.getvalue()).decode()
    response = client.post("/api/v1/doubts/ask", headers=headers, json={
        "image": {"mime_type": "image/png", "data": data},
    })
    assert response.status_code == 200
    assert "2x + 3 = 11" in fake_rag.calls[0]["question"]
    assert fake_rag.calls[0]["image_data"] is not None
    saved = client.get(
        f"/api/v1/doubts/conversations/{response.json()['conversation_id']}", headers=headers
    ).json()
    assert "2x + 3 = 11" in saved["messages"][0]["content"]
    assert data not in str(saved)
    profile = client.get("/api/v1/doubts/personalization", headers=headers).json()
    assert profile["topics"] == [{"name": "Algebra", "count": 1}]


def test_invalid_image_does_not_call_ai_and_releases_request_slot(
    client: TestClient, fake_rag: FakeRagService,
) -> None:
    headers = register(client, "invalid-image@example.com")
    invalid = client.post("/api/v1/doubts/ask", headers=headers, json={
        "image": {"mime_type": "image/png", "data": "!!!!"},
    })
    assert invalid.status_code == 422
    assert not fake_rag.calls
    retry = client.post(
        "/api/v1/doubts/ask", headers=headers, json={"question": "What is climate?"}
    )
    assert retry.status_code == 200


def test_private_memory_persists_between_chats_and_respects_pause_and_reset(
    client: TestClient, fake_rag: FakeRagService,
) -> None:
    owner = register(client, "memory@example.com")
    other = register(client, "separate-memory@example.com")
    path = "/api/v1/doubts/personalization"
    style = client.patch(path, headers=owner, json={"explanation_style": "concise"})
    assert style.status_code == 200
    client.post("/api/v1/doubts/ask", headers=owner, json={"question": "What is climate?"})
    profile = client.get(path, headers=owner).json()
    assert profile["total_questions"] == 1
    assert profile["topics"] == [{"name": "Geography", "count": 1}]
    assert "weather and climate" in profile["suggested_questions"][0]
    assert client.get(path, headers=other).json()["topics"] == []
    client.post("/api/v1/doubts/ask", headers=owner, json={"question": "Explain a monsoon"})
    assert "Geography" in fake_rag.calls[-1]["personalization"]
    assert "brief" in fake_rag.calls[-1]["personalization"]
    client.patch(path, headers=owner, json={"enabled": False})
    client.post("/api/v1/doubts/ask", headers=owner, json={"question": "Explain English grammar"})
    assert fake_rag.calls[-1]["personalization"] == "No saved study preferences."
    assert client.get(path, headers=owner).json()["total_questions"] == 2
    cleared = client.delete(path, headers=owner).json()
    assert cleared["topics"] == []
    assert cleared["total_questions"] == 0
    assert cleared["enabled"] is False


def test_failed_uploads_are_throttled_without_consuming_ai_calls(
    client: TestClient, fake_rag: FakeRagService,
) -> None:
    headers = register(client, "burst@example.com")
    for _ in range(4):
        response = client.post("/api/v1/doubts/ask", headers=headers, json={
            "image": {"mime_type": "image/png", "data": "!!!!"},
        })
        assert response.status_code == 422
    # Clearing study memory must not clear request throttling.
    client.delete("/api/v1/doubts/personalization", headers=headers)
    blocked = client.post(
        "/api/v1/doubts/ask", headers=headers, json={"question": "What is climate?"}
    )
    assert blocked.status_code == 429
    assert fake_rag.calls == []


def test_provider_failure_rolls_back_chat_and_releases_lease(
    client: TestClient, fake_rag: FakeRagService, monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = register(client, "provider-failure@example.com")
    original_answer = fake_rag.answer

    async def unavailable(*_args: object, **_kwargs: object) -> RagAnswer:
        raise RagUnavailableError("The answer service is temporarily unavailable.")

    monkeypatch.setattr(fake_rag, "answer", unavailable)
    failed = client.post(
        "/api/v1/doubts/ask", headers=headers, json={"question": "What is climate?"}
    )
    assert failed.status_code == 503
    assert client.get("/api/v1/doubts/personalization", headers=headers).json()[
        "total_questions"
    ] == 0
    monkeypatch.setattr(fake_rag, "answer", original_answer)
    retry = client.post(
        "/api/v1/doubts/ask", headers=headers, json={"question": "What is climate?"}
    )
    assert retry.status_code == 200
