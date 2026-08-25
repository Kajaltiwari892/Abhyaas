import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, password_digest: str) -> bool:
    return password_hash.verify(password, password_digest)


def create_access_token(user_id: str) -> tuple[str, datetime]:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_minutes)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": secrets.token_urlsafe(16),
        "iat": datetime.now(UTC),
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), expires_at


def decode_access_token(token: str) -> str:
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"require": ["sub", "type", "jti", "iat", "exp", "iss", "aud"]},
    )
    if payload.get("type") != "access" or not payload.get("sub"):
        raise jwt.InvalidTokenError("Invalid access token")
    return str(payload["sub"])


def create_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def digest_identifier(value: str) -> str:
    settings = get_settings()
    return hmac.new(settings.jwt_secret.encode(), value.encode(), hashlib.sha256).hexdigest()
