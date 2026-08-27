import ssl

from app.db.url import build_async_database_config


def test_neon_url_is_normalized_for_asyncpg() -> None:
    url, connect_args = build_async_database_config(
        "postgresql://owner:secret@example-pooler.neon.tech/neondb"
        "?sslmode=require&channel_binding=require"
    )

    assert url.drivername == "postgresql+asyncpg"
    assert "sslmode" not in url.query
    assert "channel_binding" not in url.query
    assert isinstance(connect_args["ssl"], ssl.SSLContext)
    assert connect_args["ssl"].check_hostname is True


def test_neon_psql_copy_format_is_accepted() -> None:
    url, connect_args = build_async_database_config(
        "psql 'postgresql://owner:secret@example-pooler.neon.tech/neondb"
        "?sslmode=require&channel_binding=require'"
    )

    assert url.drivername == "postgresql+asyncpg"
    assert url.username == "owner"
    assert url.database == "neondb"
    assert "ssl" in connect_args


def test_sqlite_url_is_unchanged() -> None:
    raw_url = "sqlite+aiosqlite:///test.db"

    url, connect_args = build_async_database_config(raw_url)

    assert url.render_as_string(hide_password=False) == raw_url
    assert connect_args == {}
