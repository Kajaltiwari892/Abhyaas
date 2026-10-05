import asyncio
import re
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.v1 import auth as routes
from app.auth import service
from app.core.security import digest_token
from app.db.session import SessionLocal
from app.models.auth import RefreshSession


def register(client: TestClient) -> str:
    response = client.post("/api/v1/auth/register", json={
        "name": "Session Test", "email": "session@example.com", "password": "Strongpass1",
    })
    assert response.status_code == 201
    return client.cookies.get("abhyaas_refresh")


def request_with_cookie(client: TestClient, endpoint: str, token: str):
    # Simulates a retry/browser that did not receive the last Set-Cookie response.
    return client.post(f"/api/v1/auth/{endpoint}", headers={
        "Cookie": f"abhyaas_refresh={token}",
    })


def sessions() -> list[RefreshSession]:
    async def read():
        async with SessionLocal() as db:
            return list((await db.scalars(select(RefreshSession))).all())
    return asyncio.run(read())


@pytest.fixture
def clock(monkeypatch):
    class Clock(datetime):
        current = datetime.now(UTC)

        @classmethod
        def now(cls, tz=None):
            return cls.current if tz else cls.current.replace(tzinfo=None)

    monkeypatch.setattr(service, "datetime", Clock)
    monkeypatch.setattr(routes, "datetime", Clock)
    return Clock


def test_lost_response_and_overlapping_refreshes_converge(client: TestClient):
    original = register(client)
    assert request_with_cookie(client, "refresh", original).status_code == 200
    replacement = client.cookies.get("abhyaas_refresh")
    assert replacement != original
    for token in (original, replacement, original, replacement):
        response = request_with_cookie(client, "refresh", token)
        assert response.status_code == 200
        assert client.cookies.get("abhyaas_refresh") == replacement
    records = sessions()
    assert len(records) == 2
    assert sum(row.revoked_at is None for row in records) == 1
    assert {row.token_digest for row in records} == {
        digest_token(original), digest_token(replacement),
    }
    assert len({row.family_id for row in records}) == 1


def test_refresh_keeps_absolute_seven_day_expiry(client: TestClient, clock):
    original = register(client)
    original_expiry = service.as_utc(sessions()[0].expires_at)
    assert original_expiry == clock.current + timedelta(days=7)
    clock.current += timedelta(days=6)
    response = request_with_cookie(client, "refresh", original)
    assert response.status_code == 200
    assert max(map(int, re.findall(r"Max-Age=(\d+)", response.headers["set-cookie"]))) == 86400
    replacement = client.cookies.get("abhyaas_refresh")
    clock.current += timedelta(minutes=10)
    assert request_with_cookie(client, "refresh", replacement).status_code == 200
    assert client.cookies.get("abhyaas_refresh") != replacement
    assert all(service.as_utc(row.expires_at) == original_expiry for row in sessions())
    latest = client.cookies.get("abhyaas_refresh")
    clock.current = original_expiry
    assert request_with_cookie(client, "refresh", latest).status_code == 401


def test_old_token_replay_revokes_only_its_login(client: TestClient, clock):
    original = register(client)
    assert request_with_cookie(client, "refresh", original).status_code == 200
    replacement = client.cookies.get("abhyaas_refresh")
    login = client.post("/api/v1/auth/login", json={
        "email": "session@example.com", "password": "Strongpass1",
    })
    assert login.status_code == 200
    other_device = client.cookies.get("abhyaas_refresh")
    clock.current += timedelta(seconds=61)
    assert request_with_cookie(client, "refresh", original).status_code == 401
    assert request_with_cookie(client, "refresh", replacement).status_code == 401
    assert request_with_cookie(client, "refresh", other_device).status_code == 200


def test_logout_with_predecessor_revokes_successor_even_during_grace(client: TestClient):
    original = register(client)
    assert request_with_cookie(client, "refresh", original).status_code == 200
    replacement = client.cookies.get("abhyaas_refresh")
    assert request_with_cookie(client, "logout", original).status_code == 200
    assert request_with_cookie(client, "refresh", original).status_code == 401
    assert request_with_cookie(client, "refresh", replacement).status_code == 401


def test_password_reset_cannot_be_undone_by_retry(client: TestClient):
    original = register(client)
    assert request_with_cookie(client, "refresh", original).status_code == 200
    replacement = client.cookies.get("abhyaas_refresh")

    async def reset():
        async with SessionLocal() as db:
            user = await service.find_user_by_email(db, "session@example.com")
            await service.set_new_password(db, user, "Newstrong2")
            await db.commit()

    asyncio.run(reset())
    assert request_with_cookie(client, "refresh", original).status_code == 401
    assert request_with_cookie(client, "refresh", replacement).status_code == 401


def test_secure_cookie_deletion_obeys_host_prefix(monkeypatch):
    monkeypatch.setattr(routes.settings, "cookie_secure", True)
    monkeypatch.setattr(routes, "REFRESH_COOKIE", "__Host-abhyaas_refresh")
    response = Response()
    routes.clear_refresh_cookie(response)
    cookies = response.headers.getlist("set-cookie")
    assert len(cookies) == 1
    assert "__Host-abhyaas_refresh=" in cookies[0]
    assert "Max-Age=0" in cookies[0]
    assert "Secure" in cookies[0]
    assert "HttpOnly" in cookies[0]
    assert "Path=/;" in cookies[0]


def test_invalid_cookie_and_untrusted_origin_do_not_create_sessions(client: TestClient):
    assert request_with_cookie(client, "refresh", "unknown").status_code == 401
    original = register(client)
    response = client.post("/api/v1/auth/refresh", headers={
        "Origin": "https://attacker.example", "Cookie": f"abhyaas_refresh={original}",
    })
    assert response.status_code == 403
    assert len(sessions()) == 1
