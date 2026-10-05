"""Check refresh locking in a disposable schema on the configured LOCAL PostgreSQL.

Run from Backend with: python -m scripts.check_refresh_concurrency
Never touches application tables; refuses remote databases.
"""
import asyncio
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.service import (
    create_refresh_session,
    locked_refresh_session,
    renew_refresh_session,
    revoke_refresh_family,
)
from app.core.config import get_settings
from app.db.url import build_async_database_config
from app.models.auth import RefreshSession, User


async def main() -> None:
    url, args = build_async_database_config(get_settings().database_url)
    if url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("This check only permits a local PostgreSQL database")
    schema = f"auth_recovery_test_{uuid.uuid4().hex}"
    admin = create_async_engine(url, connect_args=args)
    isolated = create_async_engine(url, connect_args={
        **args, "server_settings": {"search_path": schema},
    })
    session_factory = async_sessionmaker(isolated, expire_on_commit=False)
    created = False
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True
        async with isolated.begin() as connection:
            await connection.run_sync(User.__table__.create)
            await connection.run_sync(RefreshSession.__table__.create)
        async with session_factory() as db:
            user = User(name="Concurrency test", email="test@example.invalid", is_verified=True)
            db.add(user)
            await db.flush()
            original, expiry = await create_refresh_session(db, user)
            await db.commit()

        async def refresh(token):
            async with session_factory() as db:
                row = await locked_refresh_session(db, token)
                assert row is not None
                renewed = await renew_refresh_session(db, row[0], token)
                await db.commit()
                return renewed

        results = await asyncio.gather(*(refresh(original) for _ in range(8)))
        assert all(result is not None and result == results[0] for result in results)
        successor, successor_expiry = results[0]
        assert successor != original and successor_expiry == expiry
        async with session_factory() as db:
            assert await db.scalar(select(func.count()).select_from(RefreshSession)) == 2
            active = select(func.count()).select_from(RefreshSession).where(
                RefreshSession.revoked_at.is_(None)
            )
            assert await db.scalar(active) == 1

        async def logout():
            async with session_factory() as db:
                row = await locked_refresh_session(db, original)
                await revoke_refresh_family(db, row[0].family_id)
                await db.commit()

        await asyncio.gather(logout(), refresh(original), refresh(successor))
        assert await refresh(original) is None
        assert await refresh(successor) is None
        print("PASS: 8 concurrent renewals share one successor; concurrent logout stays revoked.")
    finally:
        await isolated.dispose()
        if created:
            # The identifier is generated here, never supplied by the environment/user.
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            print("Removed only the disposable auth_recovery_test schema.")
        await admin.dispose()


if __name__ == "__main__":
    asyncio.run(main())
