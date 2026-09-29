import asyncio
import base64
import hashlib
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from google.auth.exceptions import GoogleAuthError as GoogleLibraryError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from app.core.config import get_settings

GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


class GoogleSignInError(ValueError):
    """Safe public error code; never include authorization codes or tokens."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class BoundedGoogleRequest(GoogleRequest):
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        kwargs["timeout"] = 10
        return super().__call__(*args, **kwargs)


def create_google_authorization_request() -> tuple[str, str, str, str]:
    settings = get_settings()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    parameters = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge.decode(),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{urlencode(parameters)}", state, nonce, verifier


async def exchange_google_code(code: str, verifier: str, expected_nonce: str) -> dict[str, Any]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            GOOGLE_TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
        )
        if response.status_code != 200:
            try:
                error = response.json().get("error", "")
            except (ValueError, AttributeError):
                error = ""
            if error == "invalid_grant":
                raise GoogleSignInError("expired_code")
            if error in {"invalid_client", "unauthorized_client", "redirect_uri_mismatch"}:
                raise GoogleSignInError("configuration")
            raise GoogleSignInError("provider_unavailable")
        token_payload = response.json()

    encoded_id_token = token_payload.get("id_token")
    if not isinstance(encoded_id_token, str):
        raise ValueError("Google did not return an ID token")

    # Google's verifier still validates signature, audience, issuer and expiry. A small,
    # bounded tolerance avoids rejecting freshly issued tokens because of clock drift.
    try:
        claims = await asyncio.to_thread(
            id_token.verify_oauth2_token,
            encoded_id_token,
            BoundedGoogleRequest(),
            settings.google_client_id,
            clock_skew_in_seconds=60,
        )
    except GoogleLibraryError as exc:
        raise GoogleSignInError("provider_unavailable") from exc
    except ValueError as exc:
        reason = str(exc).lower()
        code = "clock_skew" if "too early" in reason or "expired" in reason else "invalid_identity"
        raise GoogleSignInError(code) from exc
    nonce = claims.get("nonce")
    if not isinstance(nonce, str) or not secrets.compare_digest(nonce, expected_nonce):
        raise ValueError("Google nonce validation failed")
    if claims.get("email_verified") is not True:
        raise ValueError("Google email is not verified")
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise GoogleSignInError("invalid_identity")
    if not isinstance(claims.get("email"), str) or "@" not in claims["email"]:
        raise GoogleSignInError("invalid_identity")
    return claims
