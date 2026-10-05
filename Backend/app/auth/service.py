import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_opaque_token,
    digest_token,
    hash_password,
    replacement_refresh_token,
)
from app.email.provider import EmailMessage, EmailProvider
from app.models.auth import EmailToken, RefreshSession, User

REFRESH_RETRY_SECONDS = 60


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def find_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == normalize_email(email)))
    return result.scalar_one_or_none()


async def create_email_token(db: AsyncSession, user: User, purpose: str) -> tuple[EmailToken, str]:
    settings = get_settings()
    await db.execute(
        update(EmailToken)
        .where(
            EmailToken.user_id == user.id,
            EmailToken.purpose == purpose,
            EmailToken.consumed_at.is_(None),
        )
        .values(consumed_at=datetime.now(UTC))
    )
    raw_token = create_opaque_token()
    token = EmailToken(
        user_id=user.id,
        purpose=purpose,
        token_digest=digest_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.email_token_minutes),
    )
    db.add(token)
    await db.flush()
    return token, raw_token


async def send_verification_email(
    db: AsyncSession, user: User, email_provider: EmailProvider
) -> None:
    settings = get_settings()
    _, raw_token = await create_email_token(db, user, "verify_email")
    link = f"{settings.frontend_url.split(',')[0]}/login?verify={raw_token}"
    await email_provider.send(
        EmailMessage(
            recipient=user.email,
            subject="Verify your Abhyaas account",
            text=f"Hello {user.name},\n\nVerify your account by opening this link:\n{link}\n\n"
            "This link expires soon. If you did not create this account, ignore this email.",
        )
    )


async def create_refresh_session(
    db: AsyncSession,
    user: User,
    expires_at: datetime | None = None,
) -> tuple[str, datetime]:
    settings = get_settings()
    session_expiry = expires_at or datetime.now(UTC) + timedelta(days=settings.refresh_token_days)
    raw_token = create_opaque_token()
    session_id = str(uuid.uuid4())
    db.add(
        RefreshSession(
            id=session_id,
            family_id=session_id,
            user_id=user.id,
            token_digest=digest_token(raw_token),
            expires_at=session_expiry,
        )
    )
    await db.flush()
    return raw_token, session_expiry


async def locked_refresh_session(
    db: AsyncSession, raw_token: str
) -> tuple[RefreshSession, User] | None:
    user_id = await db.scalar(
        select(RefreshSession.user_id).where(RefreshSession.token_digest == digest_token(raw_token))
    )
    if user_id is None:
        return None
    # One database lock covers all generations/tabs/workers of this user's session.
    # Password reset and logout acquire the same lock before revoking sessions.
    user = await db.scalar(
        select(User).where(User.id == user_id).with_for_update()
        .execution_options(populate_existing=True)
    )
    session = await db.scalar(
        select(RefreshSession).where(RefreshSession.token_digest == digest_token(raw_token))
        .execution_options(populate_existing=True)
    )
    return (session, user) if session is not None and user is not None else None


async def revoke_refresh_family(db: AsyncSession, family_id: str) -> None:
    await db.execute(
        update(RefreshSession)
        .where(RefreshSession.family_id == family_id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def renew_refresh_session(
    db: AsyncSession, session: RefreshSession, raw_token: str
) -> tuple[str, datetime] | None:
    """Rotate once; concurrent/lost-response retries return that same successor for 60s."""
    now = datetime.now(UTC)
    expiry = as_utc(session.expires_at)
    if expiry <= now:
        return None
    if session.revoked_at is not None:
        # Explicit logout/reset has no usable successor. Never revive it through grace.
        if not session.replacement_id:
            return None
        age = (now - as_utc(session.revoked_at)).total_seconds()
        successor = await db.get(RefreshSession, session.replacement_id)
        token = replacement_refresh_token(raw_token, session.replacement_id)
        if (
            0 <= age < REFRESH_RETRY_SECONDS
            and successor is not None
            and successor.family_id == session.family_id
            and successor.user_id == session.user_id
            and successor.revoked_at is None
            and as_utc(successor.expires_at) == expiry
            and secrets.compare_digest(successor.token_digest, digest_token(token))
        ):
            return token, expiry
        # Older-token replay invalidates this login, not other devices' sessions.
        await revoke_refresh_family(db, session.family_id)
        return None
    # Don't rotate the successor again during its predecessor's retry window:
    # out-of-order Set-Cookie responses must all converge on the same cookie.
    if session.id != session.family_id and (
        0 <= (now - as_utc(session.created_at)).total_seconds() < REFRESH_RETRY_SECONDS
    ):
        return raw_token, expiry
    replacement_id = str(uuid.uuid4())
    token = replacement_refresh_token(raw_token, replacement_id)
    session.revoked_at = now
    session.replacement_id = replacement_id
    db.add(RefreshSession(
        id=replacement_id,
        family_id=session.family_id,
        user_id=session.user_id,
        token_digest=digest_token(token),
        expires_at=expiry,
        created_at=now,
    ))
    await db.flush()
    return token, expiry


async def consume_email_token(
    db: AsyncSession, raw_token: str, purpose: str
) -> tuple[EmailToken, User] | None:
    result = await db.execute(
        select(EmailToken, User)
        .join(User, User.id == EmailToken.user_id)
        .where(
            EmailToken.token_digest == digest_token(raw_token),
            EmailToken.purpose == purpose,
            EmailToken.consumed_at.is_(None),
        )
    )
    row = result.one_or_none()
    if row is None:
        return None
    token, user = row
    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        return None
    token.consumed_at = datetime.now(UTC)
    return token, user


async def revoke_user_sessions(db: AsyncSession, user_id: str) -> None:
    await db.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def set_new_password(db: AsyncSession, user: User, password: str) -> None:
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    user.password_hash = hash_password(password)
    await revoke_user_sessions(db, user.id)
