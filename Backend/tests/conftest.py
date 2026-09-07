import asyncio
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DATABASE = Path(__file__).parent / "test_auth.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DATABASE.as_posix()}"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-auth"
os.environ["FRONTEND_URL"] = "http://localhost:3000"
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""
os.environ["GEMINI_API_KEY"] = ""

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


async def reset_database() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True)
def clean_database() -> None:
    asyncio.run(reset_database())


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def pytest_sessionfinish() -> None:
    asyncio.run(engine.dispose())
    TEST_DATABASE.unlink(missing_ok=True)
