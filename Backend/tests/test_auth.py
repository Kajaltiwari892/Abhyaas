import re

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import auth as auth_routes
from app.email.provider import EmailMessage


class CapturingEmailProvider:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


class FailingEmailProvider:
    async def send(self, message: EmailMessage) -> None:
        raise RuntimeError("SMTP unavailable")


def extract_query_token(message: EmailMessage, parameter: str) -> str:
    match = re.search(rf"[?&]{parameter}=([^\s]+)", message.text)
    assert match is not None
    return match.group(1)


def register_user(client: TestClient, provider: CapturingEmailProvider) -> dict:
    auth_routes.get_email_provider = lambda: provider
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "CDS Aspirant", "email": "student@example.com", "password": "Strongpass1"},
    )
    assert response.status_code == 201
    return response.json()


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_login_and_current_user(client: TestClient) -> None:
    provider = CapturingEmailProvider()
    registration = register_user(client, provider)
    assert registration["user"]["is_verified"] is True
    assert registration["access_token"]
    assert provider.messages == []

    cookie_header = client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "Strongpass1"},
    ).headers["set-cookie"]
    assert "HttpOnly" in cookie_header
    assert "SameSite=lax" in cookie_header
    assert "Path=/" in cookie_header
    assert max(map(int, re.findall(r"Max-Age=(\d+)", cookie_header))) >= 604_700

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "STUDENT@example.com", "password": "Strongpass1"},
    )
    assert login.status_code == 200
    payload = login.json()
    assert payload["user"]["email"] == "student@example.com"
    assert payload["user"]["is_verified"] is True
    assert client.cookies.get("abhyaas_refresh")

    current_user = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert current_user.status_code == 200
    assert current_user.json()["name"] == "CDS Aspirant"

    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"] != payload["access_token"]

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert client.cookies.get("abhyaas_refresh") is None


def test_duplicate_registration_is_rejected(client: TestClient) -> None:
    provider = CapturingEmailProvider()
    register_user(client, provider)
    duplicate = client.post(
        "/api/v1/auth/register",
        json={"name": "Another User", "email": "student@example.com", "password": "Strongpass2"},
    )
    assert duplicate.status_code == 409


def test_forgot_and_reset_password(client: TestClient) -> None:
    provider = CapturingEmailProvider()
    register_user(client, provider)

    forgot = client.post("/api/v1/auth/forgot-password", json={"email": "student@example.com"})
    assert forgot.status_code == 200
    reset_token = extract_query_token(provider.messages[-1], "reset")

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "password": "Newstrong2"},
    )
    assert reset.status_code == 200
    reused = client.post(
        "/api/v1/auth/reset-password", json={"token": reset_token, "password": "Changedagain3"},
    )
    assert reused.status_code == 400
    assert client.post("/api/v1/auth/refresh").status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "Newstrong2"},
    )
    assert login.status_code == 200


def test_forgot_password_email_failure_returns_cors_safe_response(client: TestClient) -> None:
    provider = CapturingEmailProvider()
    register_user(client, provider)
    auth_routes.get_email_provider = lambda: FailingEmailProvider()

    response = client.post(
        "/api/v1/auth/forgot-password",
        headers={"Origin": "http://localhost:3000"},
        json={"email": "student@example.com"},
    )

    assert response.status_code == 503
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.json()["detail"] == (
        "We could not send the reset email right now. Please try again shortly."
    )


def test_protected_route_and_origin_checks(client: TestClient) -> None:
    unauthorized = client.get("/api/v1/users/me")
    assert unauthorized.status_code == 401

    provider = CapturingEmailProvider()
    register_user(client, provider)
    untrusted_login = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://attacker.example"},
        json={"email": "student@example.com", "password": "Strongpass1"},
    )
    assert untrusted_login.status_code == 403


def test_google_sign_in_reports_missing_local_credentials(client: TestClient) -> None:
    response = client.get("/api/v1/auth/google/start", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/auth/callback?google_error=not_configured")


def test_google_oauth_cookies_are_available_to_frontend_proxy_callback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth_routes.settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(auth_routes.settings, "google_client_secret", "test-client-secret")
    monkeypatch.setattr(
        auth_routes,
        "create_google_authorization_request",
        lambda: ("https://accounts.google.com/authorize", "state", "nonce", "verifier"),
    )

    response = client.get("/api/v1/auth/google/start", follow_redirects=False)

    assert response.status_code == 303
    oauth_cookies = [
        value
        for value in response.headers.get_list("set-cookie")
        if "abhyaas_oauth_" in value
    ]
    assert len(oauth_cookies) == 3
    assert all("Path=/" in value for value in oauth_cookies)


def test_repeated_failed_logins_are_throttled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth_routes.settings, "login_attempt_limit", 2)
    provider = CapturingEmailProvider()
    register_user(client, provider)

    for _ in range(2):
        failed = client.post(
            "/api/v1/auth/login",
            json={"email": "student@example.com", "password": "Wrongpass1"},
        )
        assert failed.status_code == 401

    throttled = client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "Strongpass1"},
    )
    assert throttled.status_code == 429
    assert throttled.headers["retry-after"] == "900"
