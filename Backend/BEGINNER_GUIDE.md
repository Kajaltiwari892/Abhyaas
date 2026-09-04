# Abhyaas Backend — Beginner Guide

This guide explains the backend in plain language. You do not need to understand every file before running the project.

## 1. What happens when a user signs up?

```text
Login page in the browser
        |
        | POST /api/v1/auth/register
        v
FastAPI route validates the request
        |
        v
Authentication service hashes the password
        |
        v
SQLAlchemy saves the user in PostgreSQL
        |
        v
The backend creates a secure seven-day login session
        |
        v
The browser receives only an HttpOnly session cookie
```

The browser never connects directly to PostgreSQL. It talks to FastAPI, and FastAPI talks to PostgreSQL.

## 2. Important Python ideas used here

- A **module** is normally one `.py` file.
- A **package** is a folder containing Python modules and an `__init__.py` file.
- A **function** is reusable logic defined with `def` or `async def`.
- `async def` is used for work that waits for something, such as a database query.
- A **class** is a reusable description of data or behaviour. Database tables and validation schemas are classes here.
- A **dependency** is an installed library such as FastAPI or SQLAlchemy.
- A **virtual environment** keeps this project’s Python libraries separate from other Python projects.

## 3. File-by-file map

### Project-level files

| File | Purpose |
| --- | --- |
| `pyproject.toml` | Project information and Python dependency list. It replaces a basic `requirements.txt` and also configures pytest and Ruff. |
| `.env.example` | Safe template showing required settings. It contains no real password or secret. |
| `.env` | Your private local settings, including the PostgreSQL password and JWT secret. Git ignores it. |
| `.gitignore` | Prevents secrets, virtual environments, caches, and test databases from entering Git. |
| `Dockerfile` | Recipe for building the backend as a portable Linux container for deployment. It is not required for everyday local development. |
| `alembic.ini` | Configuration for Alembic database migrations. |
| `README.md` | Short setup and run instructions. |
| `BACKEND_PLAN.md` | Full zero-budget product and backend roadmap. |

### Application entry point

| File | Purpose |
| --- | --- |
| `app/main.py` | Creates the FastAPI application, enables CORS, and attaches all API routes. Uvicorn starts this file using `app.main:app`. |

### Core configuration and security

| File | Purpose |
| --- | --- |
| `app/core/config.py` | Reads settings from `.env`, such as the database URL, frontend URL, and token duration. |
| `app/core/security.py` | Hashes passwords with Argon2, verifies passwords, creates JWT access tokens, and hashes private session tokens. |

### Database

| File | Purpose |
| --- | --- |
| `app/db/base.py` | Defines the base class used by all SQLAlchemy database models. |
| `app/db/session.py` | Opens and closes asynchronous PostgreSQL sessions for API requests. |
| `app/models/auth.py` | Defines the `users`, `refresh_sessions`, and `email_tokens` tables as Python classes. |

### Validation schemas

| File | Purpose |
| --- | --- |
| `app/schemas/auth.py` | Defines which fields the API accepts and returns. For example, signup requires a valid email and a password with a letter and number. |

Models and schemas are different:

- A **model** describes how data is stored in PostgreSQL.
- A **schema** describes what data may enter or leave the API.

### Authentication logic

| File | Purpose |
| --- | --- |
| `app/auth/service.py` | Reusable authentication operations: normalize email, find users, create refresh sessions, create verification tokens, and reset passwords. |
| `app/auth/dependencies.py` | Reads a Bearer access token and loads the currently authenticated user for protected routes. |

### API routes

| File | Purpose |
| --- | --- |
| `app/api/v1/auth.py` | HTTP endpoints for register, verify, login, refresh, logout, forgot password, and reset password. |
| `app/api/v1/users.py` | Protected `/users/me` endpoint that returns the current user. |
| `app/api/v1/router.py` | Combines all version-one routes and provides the health endpoint. |

`v1` is included in the URL so we can build a future `v2` without suddenly breaking older clients.

### Email

| File | Purpose |
| --- | --- |
| `app/email/provider.py` | Defines a common email interface. The current console provider prints links in the terminal and sends nothing externally. A free real provider can be added later without changing authentication logic. |

### Database migrations

| File | Purpose |
| --- | --- |
| `alembic/env.py` | Connects Alembic to the configured database and SQLAlchemy models. |
| `alembic/versions/20260821_01_auth.py` | First migration: creates authentication tables and indexes. |

A migration is a version-controlled database change. We use migrations instead of manually creating tables in pgAdmin.

### Tests

| File | Purpose |
| --- | --- |
| `tests/conftest.py` | Creates an isolated temporary test database and test client. |
| `tests/test_auth.py` | Tests signup, verification, login, current user, refresh, logout, duplicate signup, and password reset. |

Tests deliberately use a temporary SQLite file so they cannot damage your real PostgreSQL data. The running application uses PostgreSQL.

### Helper scripts

| File | Purpose |
| --- | --- |
| `scripts/setup_local_postgres.ps1` | Securely asks for your local PostgreSQL password, creates the `abhyaas` database, creates `.env`, and runs migrations. |
| `scripts/setup_local_postgres.cmd` | Double-clickable Windows launcher for the PostgreSQL setup script. |
| `scripts/start_backend.ps1` | Starts FastAPI using the project virtual environment and local `.env`. |
| `scripts/start_backend_background.ps1` | Starts FastAPI as one persistent hidden local process and checks that it is healthy. |

### Frontend authentication files

| File | Purpose |
| --- | --- |
| `Frontend/abhyaas/lib/auth-api.ts` | Small browser client for calling the FastAPI authentication endpoints. |
| `Frontend/abhyaas/app/login/page.tsx` | Login, signup, email verification, forgot-password, and reset-password user interface. |

## 4. Why is there a Dockerfile?

Different computers can have different Python versions and system libraries. A Dockerfile describes one repeatable environment.

This Dockerfile:

1. Starts with a small official Python 3.12 Linux image.
2. Creates `/app` inside the container.
3. Copies the project code.
4. Installs dependencies from `pyproject.toml`.
5. Exposes container port 8000. Local development uses port 8001 to avoid a stale Windows listener.
6. Starts Uvicorn and FastAPI.

You do **not** need Docker to learn Python or run the backend locally. It is mainly useful later for Render or another deployment platform.

## 5. Commands already run and why

### Create an isolated Python environment

```powershell
python -m venv .venv
```

This created `Backend/.venv`. Libraries installed here do not affect other Python projects.

### Upgrade pip

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

`pip` installs Python packages. Updating it prevents old installer bugs.

### Install the backend and development tools

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

- `-e` means editable mode: Python uses the current source code, so reinstalling after every edit is unnecessary.
- `.[dev]` installs the normal dependencies plus pytest, Ruff, HTTPX, and the temporary test database driver.

### Check Python code quality

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format .
```

Ruff finds common mistakes, sorts imports, and keeps formatting consistent.

### Run backend tests

```powershell
.\.venv\Scripts\pytest.exe -q
```

pytest executed the complete authentication flow automatically. `-q` means compact output.

### Create/update database tables

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

This applies every migration up to the latest version, called `head`.

### Start the backend

```powershell
.\scripts\start_backend.ps1
```

This runs the equivalent of:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001
```

- `app.main` means the `app/main.py` module.
- The final `app` is the FastAPI object inside that file.
- Port `8001` becomes the local backend address.

If you are actively editing Python and want automatic restarts, use:

```powershell
.\scripts\start_backend.ps1 -Reload
```

### Check the frontend

```powershell
npm run lint
npm run build
```

These commands check React/TypeScript code and prove that Next.js can create a production build.

## 6. Commands you will normally use

Open terminal one in the `Backend` folder:

```powershell
.\scripts\start_backend.ps1
```

Open terminal two in `Frontend/abhyaas`:

```powershell
npm run dev
```

Then open:

- Website: <http://localhost:3000>
- API documentation: <http://127.0.0.1:8001/docs>
- API health: <http://127.0.0.1:8001/api/v1/health>

## 7. Do I need keys?

Not for the local authentication system.

- PostgreSQL uses the local `postgres` username and the password selected during installation.
- JWT uses a random secret generated locally by the setup script.
- Development email prints links to the backend terminal.
- Real email and Gemini keys are needed only when those external services are added later.

Never paste secret keys or database passwords into chat, screenshots, source code, or GitHub.
