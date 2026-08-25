import asyncio
import base64
import hashlib
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from app.core.config import get_settings

GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


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
        response.raise_for_status()
        token_payload = response.json()

    encoded_id_token = token_payload.get("id_token")
    if not isinstance(encoded_id_token, str):
        raise ValueError("Google did not return an ID token")

    claims = await asyncio.to_thread(
        id_token.verify_oauth2_token,
        encoded_id_token,
        GoogleRequest(),
        settings.google_client_id,
    )
    nonce = claims.get("nonce")
    if not isinstance(nonce, str) or not secrets.compare_digest(nonce, expected_nonce):
        raise ValueError("Google nonce validation failed")
    if claims.get("email_verified") is not True:
        raise ValueError("Google email is not verified")
    return claims
