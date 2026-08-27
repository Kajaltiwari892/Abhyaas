import shlex
import ssl
from typing import Any

from sqlalchemy.engine import URL, make_url


def build_async_database_config(database_url: str) -> tuple[URL, dict[str, Any]]:
    """Convert provider PostgreSQL URLs into SQLAlchemy asyncpg configuration."""
    database_url = database_url.strip()

    # Neon's psql copy option wraps the actual URL as: psql 'postgresql://...'.
    # Accept that format without requiring the secret to be copied again.
    if database_url.casefold().startswith("psql "):
        command_parts = shlex.split(database_url)
        if len(command_parts) != 2 or command_parts[0].casefold() != "psql":
            raise ValueError("DATABASE_URL contains an invalid psql command")
        database_url = command_parts[1]
    elif (
        len(database_url) >= 2
        and database_url[0] == database_url[-1]
        and database_url[0] in {"'", '"'}
    ):
        database_url = database_url[1:-1]

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    url = make_url(database_url)
    connect_args: dict[str, Any] = {}

    if url.drivername in {"postgresql", "postgresql+asyncpg"}:
        url = url.set(drivername="postgresql+asyncpg")
        query = dict(url.query)
        ssl_mode = query.pop("sslmode", None)

        # asyncpg does not accept libpq's channel_binding URL parameter.
        query.pop("channel_binding", None)
        url = url.set(query=query)

        if ssl_mode and ssl_mode != "disable":
            # Neon uses publicly trusted certificates. The default context
            # verifies both the certificate chain and database hostname.
            connect_args["ssl"] = ssl.create_default_context()

    return url, connect_args
