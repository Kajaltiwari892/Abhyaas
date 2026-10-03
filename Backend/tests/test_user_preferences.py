import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def register(client, email="target@example.com"):
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Study Target", "email": email, "password": "Strongpass1"},
    )
    assert response.status_code == 201
    return response.json()


def headers(session):
    return {"Authorization": f"Bearer {session['access_token']}"}


@pytest.mark.parametrize("academy", ["ima", "ina", "afa", "ota"])
def test_target_is_saved_and_survives_login_and_refresh(client, academy):
    session = register(client)
    assert session["user"]["target_academy"] is None
    result = client.patch(
        "/api/v1/users/me/preferences",
        headers=headers(session), json={"target_academy": academy},
    )
    assert result.status_code == 200
    assert result.json()["target_academy"] == academy
    assert result.json()["id"] == session["user"]["id"]
    assert client.get("/api/v1/users/me", headers=headers(session)).json()[
        "target_academy"
    ] == academy
    login = client.post(
        "/api/v1/auth/login", json={"email": "target@example.com", "password": "Strongpass1"}
    )
    assert login.status_code == 200
    assert login.json()["user"]["target_academy"] == academy
    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["user"]["target_academy"] == academy


def test_target_can_change_and_clear_without_affecting_another_account(client):
    first = register(client)
    second = register(client, "other@example.com")
    for target in ["ota", "ima", None]:
        result = client.patch(
            "/api/v1/users/me/preferences", headers=headers(first),
            json={"target_academy": target},
        )
        assert result.status_code == 200
        assert result.json()["target_academy"] == target
        assert client.get("/api/v1/users/me", headers=headers(second)).json()[
            "target_academy"
        ] is None


@pytest.mark.parametrize("payload", [
    {}, {"target_academy": "unknown"}, {"target_academy": "OTA"},
    {"target_academy": 1}, {"target_academy": "ota", "user_id": "another-user"},
    {"target_academy": "ota", "is_verified": True},
])
def test_invalid_preferences_are_rejected_without_mutation(client, payload):
    session = register(client)
    result = client.patch(
        "/api/v1/users/me/preferences", headers=headers(session), json=payload,
    )
    assert result.status_code == 422
    assert client.get("/api/v1/users/me", headers=headers(session)).json()[
        "target_academy"
    ] is None


def test_preferences_require_bearer_auth_even_with_session_cookie(client):
    register(client)
    result = client.patch("/api/v1/users/me/preferences", json={"target_academy": "ota"})
    assert result.status_code == 401


def test_migration_preserves_existing_rows_and_rejects_invalid_targets():
    path = Path(__file__).parents[1] / "alembic/versions/20261003_19_academy_preference.py"
    spec = importlib.util.spec_from_file_location("academy_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT)"))
        connection.execute(sa.text("INSERT INTO users VALUES ('existing', 'Keep my name')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        row = connection.execute(sa.text("SELECT * FROM users")).mappings().one()
        assert dict(row) == {"id": "existing", "name": "Keep my name", "target_academy": None}
        connection.execute(sa.text("UPDATE users SET target_academy = 'ota'"))
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(sa.text("UPDATE users SET target_academy = 'bad'"))
    engine.dispose()
