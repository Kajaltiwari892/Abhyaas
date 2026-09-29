import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.auth import google


def exchange(claims: dict, *, nonce: str = "expected") -> dict:
    async def scenario() -> dict:
        client = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"id_token": "signed-token"})
        ))
        with patch.object(google.httpx, "AsyncClient", return_value=client), patch.object(
            google.id_token, "verify_oauth2_token", return_value=claims,
        ) as verifier:
            result = await google.exchange_google_code("code", "pkce", nonce)
            assert verifier.call_args.kwargs["clock_skew_in_seconds"] == 60
            assert verifier.call_args.args[0] == "signed-token"
            assert verifier.call_args.args[2] == google.get_settings().google_client_id
            return result
    return asyncio.run(scenario())


def test_google_verified_identity_with_bounded_clock_tolerance() -> None:
    claims = {"sub": "123", "email": "student@example.com", "email_verified": True,
              "nonce": "expected"}
    assert exchange(claims) == claims


@pytest.mark.parametrize("change", [
    {"nonce": "wrong"}, {"email_verified": False}, {"email_verified": "true"},
    {"sub": ""}, {"email": None},
])
def test_google_rejects_invalid_claims(change: dict) -> None:
    with pytest.raises(ValueError):
        exchange({"sub": "123", "email": "student@example.com", "email_verified": True,
                  "nonce": "expected", **change})


def test_google_expired_code_has_actionable_safe_error() -> None:
    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda _request: httpx.Response(400, json={"error": "invalid_grant"})
        ))
        with (
            patch.object(google.httpx, "AsyncClient", return_value=client),
            pytest.raises(google.GoogleSignInError, match="expired_code"),
        ):
            await google.exchange_google_code("private-code", "private-verifier", "nonce")
    asyncio.run(scenario())
