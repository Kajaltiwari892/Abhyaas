# Abhyaas Backend

FastAPI authentication backend for Abhyaas.

New to Python? Read [BEGINNER_GUIDE.md](BEGINNER_GUIDE.md) for a plain-language explanation of every file and command.

To enable Google sign-in, follow [GOOGLE_AUTH_SETUP.md](GOOGLE_AUTH_SETUP.md).

To send real password-reset emails, follow [EMAIL_SETUP.md](EMAIL_SETUP.md).

## Quick local setup

PostgreSQL 18.6 is installed on this computer. From the `Backend` folder, run:

```powershell
.\scripts\setup_local_postgres.ps1
```

If you prefer, double-click `scripts\setup_local_postgres.cmd` in File Explorer instead of entering the PowerShell command.

Enter the private PostgreSQL password selected during installation. The script creates the database, generates `.env`, and applies migrations. After that, start the persistent local API with:

```powershell
.\scripts\start_backend.ps1
```

The command starts the backend in the background, so it stays available after
the terminal closes. For foreground debugging with automatic code reloads, use:

```powershell
.\scripts\start_backend.ps1 -Foreground
```

After creating or replacing a Google App Password, update the local SMTP
credential without displaying it in the terminal:

```powershell
.\scripts\set_local_smtp_password.ps1
```

This saves the credential in the ignored local `.env` file and restarts the
background backend on port 8001.

The command is safe to run again: it reports when a healthy backend is already
listening instead of starting a duplicate process.

## Included now

### Full-paper solutions in the doubt solver

Requests such as `Solve CDS I 2026 English full paper` go directly to the stored
paper questions, not to a RAG paper-summary excerpt. The solver includes the full
options, directions and passages and returns at most ten solutions per response.
`Continue solving` resumes the saved position; `Explain Q3` revisits a question
without losing that position. A new subject or ordinary lesson does not inherit
an old paper search.

The existing conversation-message JSON stores a `paper_solution` snapshot, so
this feature needs no database migration. AI solutions never update paper answer
keys, verification flags, mock-test scores or other students' conversations.
Verified keys and unverified AI reasoning have separate visible labels. Missing
text/diagrams, uncertainty and key conflicts remain explicit; provider failures
do not advance the cursor or become misleading paper-summary answers.

Run `python -m pytest tests/test_paper_solver.py` for isolated checks. Run
`python scripts/check_paper_solver.py` for a read-only local source check; adding
`--live` sends one ten-question batch to the configured AI provider (uses quota).
The background local backend does not auto-reload code: restart it after changes.

### Authentication

- Registration with normalized unique email addresses.
- Argon2 password hashing.
- Login with 15-minute, issuer-and-audience-bound JWT access tokens kept only in memory.
- Rotating seven-day refresh sessions stored as hashes in PostgreSQL.
- Secure, HttpOnly refresh cookie.
- Google OpenID Connect sign-in with authorization code, PKCE, state, and nonce validation.
- PostgreSQL-backed throttling after repeated failed sign-in attempts.
- Logout and current-user endpoints.
- Forgot/reset password flow.
- Console email provider for local development and authenticated SMTP delivery in production.
- PostgreSQL migration and automated authentication tests.

The seven-day limit is measured from sign-in, not extended on every visit. The
frontend renews the short-lived access token before expiry and on return to the
tab. Network failures keep the current UI/session and retry with bounded backoff;
only a confirmed invalid refresh cookie sends the student back to sign-in.
Protected API requests can renew and retry once after a 401. Network/5xx failures
of writes are never automatically replayed, to avoid duplicate saves/submissions.

Migration `20261005_20` adds refresh-session lineage without resetting existing
expiry dates. Renewals take a PostgreSQL user-row lock. For 60 seconds, a retry of
the immediate predecessor returns the same successor, allowing recovery after a
lost response. Only token hashes are stored. Older-token reuse revokes that login
family; logout and password reset cannot be reversed by the retry window.

Apply `alembic upgrade head` and restart the backend when installing this change.
Already invalidated cookies may require one new sign-in. Deploy both backend and
frontend for the live site to receive the complete fix; changing localhost alone
does not update production. Keep `JWT_SECRET` stable across deployments.

Run `python -m pytest tests/test_auth.py tests/test_refresh_recovery.py` for auth
regressions. `python -m scripts.check_refresh_concurrency` checks eight overlapping
renewals and concurrent logout in a disposable local PostgreSQL schema, removes
only that schema afterward, and refuses remote databases. Frontend recovery and
request-replay checks run with `node --test tests/*.test.mjs` in `Frontend/abhyaas`.

## Manual setup reference

### 1. Install PostgreSQL on Windows

The installer currently downloaded on this computer is:

```text
C:\Users\kanja\Downloads\postgresql-18.6-1-windows-x64.exe
```

Run it and use these choices:

1. Install `PostgreSQL Server`, `pgAdmin 4`, and `Command Line Tools`.
2. Keep the installation and data directories at their defaults.
3. Create a strong password for the `postgres` administrator. Save it in your password manager.
4. Keep port `5432` unless the installer says it is already used.
5. Keep the default locale.
6. Stack Builder is optional and can be skipped.

No external database API key is needed for local PostgreSQL. The password chosen during installation is the credential.

### 2. Create the database

Open **SQL Shell (psql)** from the Start menu. Press Enter for the default server, database, port, and username, then enter the password chosen during installation.

Run:

```sql
CREATE DATABASE abhyaas;
```

Then exit with:

```text
\q
```

### 3. Configure the backend

From the `Backend` folder:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Open `.env` locally and:

1. Replace `YOUR_PASSWORD` in `DATABASE_URL` with the PostgreSQL password.
2. Replace `JWT_SECRET` with the generated random value.

Do not share `.env` and do not commit it.

### 4. Install and start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Open API documentation at <http://localhost:8001/docs>.

Development verification and password-reset links are printed in the backend terminal. No email account or API key is required yet.

### 5. Run tests

```powershell
pytest
ruff check .
```

The tests use a temporary SQLite database. The actual application configuration remains PostgreSQL.

## API routes

```text
GET  /api/v1/health
POST /api/v1/auth/register
POST /api/v1/auth/verify-email
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/google/start
GET  /api/v1/auth/google/callback
POST /api/v1/auth/forgot-password
POST /api/v1/auth/reset-password
GET  /api/v1/users/me
PATCH /api/v1/users/me/preferences
```

## Saved academy target

`PATCH /api/v1/users/me/preferences` requires the student's bearer token and accepts
only `{"target_academy":"ota"}` (or `ima`, `ina`, `afa`). Send an explicit `null`
to clear the target. The saved value is returned by `/users/me`, login and session
refresh. Other account fields and user IDs are rejected by this endpoint.

Apply `alembic upgrade head` before running the updated backend. Migration
`20261003_19` adds a nullable, constrained column; existing accounts start without
a target. It does not change practice sets, answers, scores, or chat memory.

The frontend uses this preference to prioritise English and GK for OTA, or all
three written subjects for IMA/INA/AFA. Browsing an academy never saves a target;
students must use **Set … as my target**. Optional subjects and all history remain
accessible. This is a study preference, not an eligibility assessment or AI training.
