# Deploying Abhyaas on Vercel

Abhyaas is a monorepo with two applications. Create **two Vercel projects** from
the same Git repository.

## 1. Create a hosted PostgreSQL database

The PostgreSQL server installed on your computer only works locally. A Vercel
deployment needs a hosted database. Neon has a free PostgreSQL plan that is
enough for initial development.

1. Create a Neon account and project.
2. Copy its pooled connection string. Never commit this string to Git or paste
   it into chat.
3. Use the standard `postgresql://...` value exactly as Neon supplies it. The
   backend converts it to an asyncpg connection safely and preserves verified
   TLS.

## 2. Deploy the FastAPI backend

Import the repository into Vercel as a new project.

- Project name: `abhyaas-backend` (or another name)
- Root Directory: `Backend`
- Framework preset: FastAPI, if shown
- Build Command: leave empty/default
- Output Directory: leave empty

Add these Production environment variables:

```text
APP_ENV=production
APP_NAME=Abhyaas API
API_V1_PREFIX=/api/v1
FRONTEND_URL=https://YOUR-FRONTEND.vercel.app
DATABASE_URL=YOUR_NEON_ASYNCPG_CONNECTION_STRING
JWT_SECRET=GENERATE_A_LONG_RANDOM_SECRET
JWT_ISSUER=abhyaas-api
JWT_AUDIENCE=abhyaas-web
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7
LOGIN_ATTEMPT_LIMIT=5
LOGIN_ATTEMPT_WINDOW_MINUTES=15
EMAIL_TOKEN_MINUTES=30
EMAIL_PROVIDER=console
COOKIE_SECURE=true
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://YOUR-FRONTEND.vercel.app/backend-api/auth/google/callback
```

Generate `JWT_SECRET` in PowerShell:

```powershell
[Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(64))
```

Deploy, then confirm this URL returns a successful response:

```text
https://YOUR-BACKEND.vercel.app/api/v1/health
```

## 3. Create the production database tables

From the local `Backend` directory, temporarily set the hosted connection string
and run Alembic. Do not paste the connection string into chat or commit it.

```powershell
$env:DATABASE_URL="YOUR_NEON_ASYNCPG_CONNECTION_STRING"
.\.venv\Scripts\alembic.exe upgrade head
Remove-Item Env:DATABASE_URL
```

## 4. Deploy the Next.js frontend

Import the same repository into Vercel again as a second project.

- Project name: `abhyaas` (or another name)
- Root Directory: `Frontend/abhyaas`
- Framework preset: Next.js
- Build Command: default (`npm run build`)
- Output Directory: leave empty/default

Add these Production environment variables:

```text
NEXT_PUBLIC_API_URL=/backend-api
BACKEND_API_ORIGIN=https://YOUR-BACKEND.vercel.app
```

The `/backend-api` rewrite makes browser requests same-origin. This allows the
secure HttpOnly authentication cookie and Google OAuth state cookie to work
without weakening their security settings.

Redeploy the frontend after changing either variable. `NEXT_PUBLIC_*` values are
inserted during the Next.js build.

## 5. Finish Google OAuth later

In Google Cloud Console, use:

- Authorized JavaScript origin: `https://YOUR-FRONTEND.vercel.app`
- Authorized redirect URI:
  `https://YOUR-FRONTEND.vercel.app/backend-api/auth/google/callback`

Put the client ID and secret only in the backend Vercel project's environment
variables, then redeploy the backend.

## What the route list means

The `○ (Static) prerendered as static content` route list is a successful Next.js
build summary. It is not the deployment error. If Vercel still marks the
deployment as failed, copy the first red error shown **after** that summary.
