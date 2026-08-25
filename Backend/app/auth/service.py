from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_opaque_token, digest_token, hash_password
from app.email.provider import EmailMessage, EmailProvider
from app.models.auth import EmailToken, RefreshSession, User


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
    db.add(
        RefreshSession(
            user_id=user.id,
            token_digest=digest_token(raw_token),
            expires_at=session_expiry,
        )
    )
    await db.flush()
    return raw_token, session_expiry


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
    user.password_hash = hash_password(password)
    await revoke_user_sessions(db, user.id)
