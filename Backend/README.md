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

Enter the private PostgreSQL password selected during installation. The script creates the database, generates `.env`, and applies migrations. After that, start the API with:

```powershell
.\scripts\start_backend.ps1
```

## Included now

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
```
