import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.google import (
    GoogleSignInError,
    create_google_authorization_request,
    exchange_google_code,
)
from app.auth.service import (
    consume_email_token,
    create_email_token,
    create_refresh_session,
    find_user_by_email,
    locked_refresh_session,
    normalize_email,
    renew_refresh_session,
    revoke_refresh_family,
    set_new_password,
)
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    digest_identifier,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.email.provider import EmailMessage, get_email_provider
from app.models.auth import LoginAttempt, User
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)
settings = get_settings()
REFRESH_COOKIE = "__Host-abhyaas_refresh" if settings.cookie_secure else "abhyaas_refresh"
OAUTH_STATE_COOKIE = "abhyaas_oauth_state"
OAUTH_NONCE_COOKIE = "abhyaas_oauth_nonce"
OAUTH_VERIFIER_COOKIE = "abhyaas_oauth_verifier"
DUMMY_PASSWORD_HASH = hash_password("invalid-password-123")
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]
TrustedOriginHeader = Annotated[str | None, Header(alias="Origin")]


async def require_trusted_origin(origin: TrustedOriginHeader = None) -> None:
    if origin is not None and origin not in settings.cors_origins:
        raise HTTPException(status_code=403, detail="Request origin is not allowed")


TrustedOrigin = Annotated[None, Depends(require_trusted_origin)]


def set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    max_age = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
    if not settings.cookie_secure:
        response.delete_cookie(key=REFRESH_COOKIE, path=f"{settings.api_v1_prefix}/auth")
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        expires=expires_at,
        max_age=max_age,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax"
    )
    if not settings.cookie_secure:
        response.delete_cookie(key=REFRESH_COOKIE, path=f"{settings.api_v1_prefix}/auth")


def set_oauth_cookie(response: Response, key: str, value: str) -> None:
    response.set_cookie(
        key=key,
        value=value,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=600,
        path="/",
    )


def clear_oauth_cookies(response: Response) -> None:
    for key in (OAUTH_STATE_COOKIE, OAUTH_NONCE_COOKIE, OAUTH_VERIFIER_COOKIE):
        response.delete_cookie(key=key, path="/")
        response.delete_cookie(key=key, path=f"{settings.api_v1_prefix}/auth/google")


def frontend_auth_redirect(error: str | None = None) -> RedirectResponse:
    frontend = settings.frontend_url.split(",")[0].rstrip("/")
    suffix = f"?google_error={error}" if error else ""
    response = RedirectResponse(f"{frontend}/auth/callback{suffix}", status_code=303)
    clear_oauth_cookies(response)
    return response


def get_login_attempt_key(email: str, request: Request) -> tuple[str, str]:
    client_ip = request.client.host if request.client else "unknown"
    return digest_identifier(normalize_email(email)), digest_identifier(client_ip)


async def enforce_login_throttle(db: AsyncSession, email: str, request: Request) -> tuple[str, str]:
    email_digest, ip_digest = get_login_attempt_key(email, request)
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.login_attempt_window_minutes)
    await db.execute(delete(LoginAttempt).where(LoginAttempt.created_at < cutoff))
    result = await db.execute(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.email_digest == email_digest,
            LoginAttempt.ip_digest == ip_digest,
            LoginAttempt.created_at >= cutoff,
        )
    )
    if result.scalar_one() >= settings.login_attempt_limit:
        raise HTTPException(
            status_code=429,
            detail="Too many sign-in attempts. Please wait before trying again",
            headers={"Retry-After": str(settings.login_attempt_window_minutes * 60)},
        )
    return email_digest, ip_digest


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, response: Response, db: DatabaseSession, _origin: TrustedOrigin
) -> AuthResponse:
    if await find_user_by_email(db, str(payload.email)) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(
        name=payload.name,
        email=normalize_email(str(payload.email)),
        password_hash=hash_password(payload.password),
        is_verified=True,
    )
    db.add(user)
    try:
        await db.flush()
        refresh_token, refresh_expires_at = await create_refresh_session(db, user)
        access_token, access_expires_at = create_access_token(user.id)
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        ) from error

    set_refresh_cookie(response, refresh_token, refresh_expires_at)
    return AuthResponse(
        access_token=access_token,
        expires_at=access_expires_at,
        user=UserResponse.model_validate(user),
    )


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(payload: VerifyEmailRequest, db: DatabaseSession) -> MessageResponse:
    consumed = await consume_email_token(db, payload.token, "verify_email")
    if consumed is None:
        raise HTTPException(status_code=400, detail="This verification link is invalid or expired")
    _, user = consumed
    user.is_verified = True
    await db.commit()
    return MessageResponse(message="Email verified. You can now sign in.")


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: DatabaseSession,
    _origin: TrustedOrigin,
) -> AuthResponse:
    email_digest, ip_digest = await enforce_login_throttle(db, str(payload.email), request)
    user = await find_user_by_email(db, str(payload.email))
    password_digest = (
        user.password_hash if user is not None and user.password_hash else DUMMY_PASSWORD_HASH
    )
    password_is_valid = verify_password(payload.password, password_digest)
    if user is None or not password_is_valid or not user.is_active:
        db.add(LoginAttempt(email_digest=email_digest, ip_digest=ip_digest))
        await db.commit()
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    await db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.email_digest == email_digest,
            LoginAttempt.ip_digest == ip_digest,
        )
    )
    refresh_token, refresh_expires_at = await create_refresh_session(db, user)
    access_token, access_expires_at = create_access_token(user.id)
    await db.commit()
    set_refresh_cookie(response, refresh_token, refresh_expires_at)
    return AuthResponse(
        access_token=access_token,
        expires_at=access_expires_at,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    response: Response,
    db: DatabaseSession,
    _origin: TrustedOrigin,
    refresh_token: RefreshCookie = None,
) -> AuthResponse:
    unauthorized = HTTPException(status_code=401, detail="Refresh session is invalid or expired")
    if refresh_token is None:
        raise unauthorized

    row = await locked_refresh_session(db, refresh_token)
    if row is None:
        raise unauthorized
    session, user = row
    if not user.is_active:
        raise unauthorized
    renewed = await renew_refresh_session(db, session, refresh_token)
    if renewed is None:
        await db.commit()  # Persist family revocation when an old token is replayed.
        raise unauthorized
    next_refresh_token, next_refresh_expiry = renewed
    access_token, access_expires_at = create_access_token(user.id)
    await db.commit()
    set_refresh_cookie(response, next_refresh_token, next_refresh_expiry)
    return AuthResponse(
        access_token=access_token,
        expires_at=access_expires_at,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    db: DatabaseSession,
    _origin: TrustedOrigin,
    refresh_token: RefreshCookie = None,
) -> MessageResponse:
    if refresh_token is not None:
        row = await locked_refresh_session(db, refresh_token)
        if row is not None:
            await revoke_refresh_family(db, row[0].family_id)
            await db.commit()
    clear_refresh_cookie(response)
    return MessageResponse(message="Signed out successfully")


@router.get("/google/start")
async def google_start() -> Response:
    if not settings.google_auth_enabled:
        return frontend_auth_redirect("not_configured")

    authorization_url, state, nonce, verifier = create_google_authorization_request()
    response = RedirectResponse(authorization_url, status_code=303)
    set_oauth_cookie(response, OAUTH_STATE_COOKIE, state)
    set_oauth_cookie(response, OAUTH_NONCE_COOKIE, nonce)
    set_oauth_cookie(response, OAUTH_VERIFIER_COOKIE, verifier)
    return response


@router.get("/google/callback")
async def google_callback(
    db: DatabaseSession,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    stored_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE),
    stored_nonce: str | None = Cookie(default=None, alias=OAUTH_NONCE_COOKIE),
    verifier: str | None = Cookie(default=None, alias=OAUTH_VERIFIER_COOKIE),
) -> Response:
    if error or not code or not state or not stored_state or not stored_nonce or not verifier:
        return frontend_auth_redirect("cancelled")
    if not secrets.compare_digest(state, stored_state):
        return frontend_auth_redirect("invalid_state")

    try:
        claims = await exchange_google_code(code, verifier, stored_nonce)
        google_sub = str(claims["sub"])
        email = normalize_email(str(claims["email"]))
    except GoogleSignInError as exc:
        logger.warning("Google sign-in failed: %s", exc.code)
        return frontend_auth_redirect(exc.code)
    except httpx.HTTPError:
        logger.warning("Google sign-in failed: provider connection")
        return frontend_auth_redirect("provider_unavailable")
    except (KeyError, ValueError, TypeError):
        logger.warning("Google sign-in failed: invalid identity or nonce")
        return frontend_auth_redirect("failed")

    result = await db.execute(select(User).where(User.google_sub == google_sub))
    user = result.scalar_one_or_none()
    if user is None:
        user = await find_user_by_email(db, email)
    if user is not None and user.google_sub not in (None, google_sub):
        return frontend_auth_redirect("account_conflict")
    if user is not None and not user.is_active:
        return frontend_auth_redirect("account_unavailable")
    if user is None:
        user = User(
            name=str(claims.get("name") or email.split("@", 1)[0]),
            email=email,
            password_hash=None,
            google_sub=google_sub,
            is_verified=True,
        )
        db.add(user)
        await db.flush()
    else:
        user.google_sub = google_sub
        user.is_verified = True

    refresh_token, refresh_expires_at = await create_refresh_session(db, user)
    await db.commit()
    response = frontend_auth_redirect()
    set_refresh_cookie(response, refresh_token, refresh_expires_at)
    return response


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest, db: DatabaseSession) -> MessageResponse:
    user = await find_user_by_email(db, str(payload.email))
    if user is not None and user.is_active:
        settings = get_settings()
        _, raw_token = await create_email_token(db, user, "reset_password")
        link = f"{settings.frontend_url.split(',')[0]}/login?reset={raw_token}"
        try:
            await get_email_provider().send(
                EmailMessage(
                    recipient=user.email,
                    subject="Reset your Abhyaas password",
                    text=f"Hello {user.name},\n\nReset your password here:\n{link}\n\n"
                    "If you did not request this, ignore this email.",
                )
            )
        except Exception:
            await db.rollback()
            logger.exception("Password-reset email delivery failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="We could not send the reset email right now. Please try again shortly.",
            ) from None
        await db.commit()
    return MessageResponse(
        message="If an account exists for this email, a password reset link has been created."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, db: DatabaseSession) -> MessageResponse:
    consumed = await consume_email_token(db, payload.token, "reset_password")
    if consumed is None:
        raise HTTPException(
            status_code=400, detail="This password reset link is invalid or expired"
        )
    _, user = consumed
    await set_new_password(db, user, payload.password)
    await db.commit()
    return MessageResponse(message="Password updated. Sign in using your new password.")
