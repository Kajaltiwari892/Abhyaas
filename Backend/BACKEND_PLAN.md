# Abhyaas Backend Plan — ₹0 Budget Version

> Last reviewed: 19 August 2026

## 1. The non-negotiable rule

Abhyaas will be built so that **you do not have to pay for any software tool while developing and testing v1**.

However, “free” can mean three different things:

- **Open-source:** free to install and run.
- **Free tier:** free only while usage stays below a limit.
- **Trial credit:** free temporarily, then the service stops or becomes paid.

We will use open-source tools and hard-limited free plans wherever possible. We will not enable automatic paid upgrades.

## 2. Important truth about AWS email

Amazon SES is **not free forever** for a new account.

- A new AWS Free Plan currently gives credits for up to **6 months**, or until the credits finish.
- AWS requires a valid payment method during account creation.
- On the AWS **Free Plan**, AWS says the account closes when the free period ends unless it is manually upgraded.
- New SES accounts start in a sandbox. In the sandbox, emails can only be sent to verified recipients and the limit is 200 messages per day.
- Production access must be requested before SES can email normal users.
- The earlier SES-specific 3,000-message monthly free tier is no longer available to new SES customers from 21 July 2026.

### Decision for Abhyaas

The code will have a reusable `EmailProvider` interface with two adapters:

1. **Amazon SES adapter** — available because you requested AWS.
2. **Resend adapter** — recommended for the strict ₹0 launch because its current free plan allows 3,000 transactional emails per month and 100 per day, with no paid overage on the free plan.

This lets us change email providers using one environment variable without rewriting authentication.

### Safe recommendation

- Use **Resend free** for the real public v1.
- Use **AWS SES Free Plan** only if learning AWS is important to you and you accept that it is a maximum six-month setup.
- Never upgrade AWS to the Paid Plan unless you later decide that payment is acceptable.

## 3. Final ₹0 technology stack

| Need | Tool | Cost status | Limit or warning |
| --- | --- | --- | --- |
| Backend language | Python 3.12 | Free and open-source | No usage charge. |
| API framework | FastAPI | Free and open-source | No usage charge. |
| Data validation | Pydantic | Free and open-source | No usage charge. |
| Database code | SQLAlchemy + asyncpg + Alembic | Free and open-source | No usage charge. |
| Main database | Neon PostgreSQL + pgvector | ₹0 free plan | Currently 0.5 GB storage per project and monthly compute limits. No card is required for the free plan. |
| Password security | pwdlib with Argon2 | Free and open-source | Passwords will never be stored as plain text. |
| Login sessions | PyJWT access and refresh tokens | Free and open-source | Refresh token stored in a Secure, HttpOnly cookie. |
| PDF reading | pypdf/pdfplumber | Free and open-source | Preferred for a simple permissive-license starting point. |
| Scanned PDF OCR | Tesseract OCR | Free and open-source | Run only when a page has no readable text. |
| Embeddings | sentence-transformers | Free and open-source | Start with a small model to fit free-server memory. |
| Vector search | pgvector inside Neon | Included in database | No separate ChromaDB service required. |
| AI answer generation | Gemini Developer API free tier | ₹0 within free limits | Rate-limited; free-tier content may be used by Google to improve products. Never send passwords or sensitive account data. |
| Voice input/output | Browser Speech APIs | Free | Browser support and voice quality vary. |
| Backend hosting | Render free web service | ₹0 free plan | Sleeps after 15 minutes without traffic; first request can take about one minute. Filesystem is temporary. |
| Frontend hosting | Vercel Hobby | ₹0 for personal/non-commercial use | Suitable while Abhyaas remains free, personal, and non-commercial. |
| Email option A | Resend free | ₹0 within limits | 3,000 emails/month and 100/day. Recommended. |
| Email option B | Amazon SES Free Plan | Temporary credits | Maximum six months for a new AWS Free Plan; not the permanent ₹0 option. |
| Testing | pytest + HTTPX | Free and open-source | Run locally and during deployment. |
| Source control | GitHub free private repository | ₹0 free plan | Never commit secret keys. |

## 4. Tools we will not use in v1

- **Claude API:** paid usage, so it does not fit the ₹0 requirement.
- **Railway:** not selected because its current offering is not a dependable free-forever backend.
- **Paid S3 storage:** unnecessary for the first version.
- **ChromaDB service:** unnecessary because pgvector can store embeddings in Neon.
- **Redis/Celery:** unnecessary until real traffic proves that background workers are required.
- **Paid speech APIs:** browser speech is enough for the first version.
- **Microservices or Kubernetes:** too much complexity for v1.

## 5. What emails Abhyaas should send

### Required emails

1. **Verify email address** after signup.
2. **Welcome email** after successful verification.
3. **Reset password email** when the user requests it.
4. **Password changed alert** after a successful password change.

### Login email

Sending an email after every login is possible, but it can quickly consume a free quota. The recommended behavior is:

- Send a **new-device login alert** when the device or browser is unfamiliar.
- Do not send repeated emails for every normal login from the same device.

If you still want an email after every login, it can be enabled using a setting, but the daily quota will be reached sooner.

### Email safety

- Email sending must happen only after the database transaction succeeds.
- Verification and reset links use single-use, expiring, hashed tokens.
- Responses must not reveal whether an email address exists in the database.
- Failed email attempts are logged without storing secret tokens.
- Marketing email will not be sent in v1.

## 6. Simple architecture

```text
Next.js frontend
       |
       | HTTPS requests
       v
FastAPI backend on Render
       |
       +---- Neon PostgreSQL + pgvector
       |
       +---- Resend OR Amazon SES
       |
       +---- Gemini free-tier API
```

The browser receives only short-lived access information. Database credentials, email keys, and AI keys stay only on the backend.

## 7. Backend folder structure

```text
Backend/
  app/
    api/v1/             # route definitions
    core/               # settings, security and logging
    db/                 # database connection and base models
    auth/               # signup, login, verification and password reset
    email/              # templates and provider adapters
    content/            # exams, academies, subjects and topics
    practice/           # questions, sets and attempts
    progress/           # accuracy, streak and weak topics
    documents/          # PDF ingestion and source metadata
    doubts/             # retrieval, chat threads and citations
    providers/          # Gemini and embedding adapters
    main.py
  alembic/              # database migrations
  scripts/              # admin-only import scripts
  tests/
  .env.example
  Dockerfile
  pyproject.toml
```

## 8. Step-by-step development order

### Step 1 — Prepare local backend

I will:

- Create the FastAPI project and clean folder structure.
- Add configuration loading from environment variables.
- Add `/api/v1/health`.
- Configure logging, CORS, pytest, and Docker.
- Add `.env.example` with placeholder values only.

You need to:

- Confirm the public project name: `Abhyaas`.
- Confirm the frontend development URL, currently `http://localhost:3000`.

### Step 2 — Create the database

You need to:

1. Create a free Neon account.
2. Create one project named `abhyaas`.
3. Copy its PostgreSQL connection string into your local `Backend/.env` file.
4. Do **not** paste that connection string into chat or commit it to GitHub.

I will:

- Add SQLAlchemy and Alembic.
- Enable pgvector.
- Create and test migrations.
- Add the initial CDS exam, academies, subjects, and topics.

### Step 3 — Build secure accounts

I will implement:

- Signup.
- Email verification.
- Login and logout.
- Short-lived access token.
- Rotating refresh token in a Secure, HttpOnly cookie.
- Forgot-password and reset-password flow.
- Rate limiting and account validation.
- Connection with the existing login/signup UI.

You need to decide:

- Does signup require `name + email + password`? Recommended: **yes**.
- Should unverified users be blocked from practice? Recommended: **no**, but block AI and account recovery until verified.

### Step 4 — Configure email

#### Recommended ₹0 path: Resend

You need to:

1. Create a free Resend account.
2. Create an API key.
3. Put it only in your local `.env` as `RESEND_API_KEY`.
4. Initially use Resend’s testing sender; add a custom domain later only if you own one.

I will:

- Create reusable HTML and plain-text email templates.
- Add verification, welcome, reset-password, and security-alert emails.
- Add retry-safe sending and tests with a fake provider.

#### AWS SES path requested by you

You need to:

1. Create a **new AWS Free Plan**, not a Paid Plan.
2. Choose one AWS Region and keep SES resources in that Region.
3. Open Amazon SES and verify a sender email address or a domain you own.
4. Send a sandbox test only to another verified address.
5. Deploy a basic public Abhyaas URL.
6. Request SES production access and select **Transactional** email.
7. Explain in the request that emails are only for signup verification, password reset, and account security.
8. Create an IAM identity with permission to send SES email only—never use the AWS root account keys.
9. Save `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, and `SES_FROM_EMAIL` only in the backend environment settings.
10. Add a reminder before the six-month AWS Free Plan expiry. Do not upgrade if the budget must remain ₹0.

I will:

- Add the SES adapter using the AWS SDK for Python.
- Keep it disabled until the SES sender identity is verified.
- Make the provider switchable using `EMAIL_PROVIDER=resend` or `EMAIL_PROVIDER=ses`.
- Add a development mode that prints the verification URL locally instead of sending an email.

### Step 5 — CDS content and practice

You need to provide or approve:

- Official CDS syllabus links/PDFs.
- Previous-year question papers that we are legally allowed to process.
- The negative-marking and academy rules for the selected CDS cycle.
- Which reference books may be indexed privately and which content may be shown publicly.

I will build:

- Subjects and topic navigation.
- Question bank and options.
- Daily and custom practice sets.
- Timer, mark-for-review, scoring, and attempt history.
- Real streak, accuracy, and weak-topic calculations.
- Previous-paper reading and timed mock modes.

### Step 6 — PDF and RAG ingestion

For the ₹0 version, PDFs will be processed by an admin script on the development computer. We will store clean chunks and source metadata in Neon, not keep large uploaded PDFs on Render’s temporary filesystem.

I will:

- Extract normal text with pypdf/pdfplumber.
- Run Tesseract only on scanned pages.
- Preserve book, chapter, page, subject, and exam metadata.
- Split text into searchable chunks.
- Generate embeddings using a small sentence-transformers model.
- Store embeddings in pgvector.
- Prevent duplicate imports using file checksums.

You need to:

- Put approved source PDFs in a private local ingestion folder.
- Tell me the correct title, edition, subject, and chapter mapping.
- Confirm that we have permission to use each document.

### Step 7 — AI doubt solver

You need to:

1. Create a Google AI Studio account.
2. Create a Gemini API key.
3. Put it only in `Backend/.env` as `GEMINI_API_KEY`.

I will:

- Retrieve only relevant chunks for the selected exam/subject.
- Ask Gemini to answer only from retrieved evidence.
- Return book/chapter/page citations with every answer.
- Refuse or show uncertainty when evidence is insufficient.
- Store follow-up threads.
- Add per-user daily limits so the free API quota cannot be abused.

### Step 8 — Deploy without paying

You need to create free accounts for:

- GitHub.
- Neon.
- Render.
- Vercel.
- Resend, or AWS Free Plan if you choose the temporary AWS route.
- Google AI Studio.

I will:

- Deploy the frontend to Vercel Hobby.
- Deploy the FastAPI backend to a Render free web service.
- Connect Render to Neon.
- Configure exact production CORS origins.
- Add secrets through dashboard environment variables.
- Run migrations and health checks.
- Configure the frontend API URL.

Expected free-tier limitation: after 15 minutes of inactivity, Render sleeps. The first API request may take approximately one minute to wake it up.

## 9. Environment variables

```dotenv
APP_ENV=development
FRONTEND_URL=http://localhost:3000
DATABASE_URL=postgresql+asyncpg://...
JWT_SECRET=generate-a-long-random-value
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=30

EMAIL_PROVIDER=console
EMAIL_FROM=Abhyaas <no-reply@example.com>

# Add only for Resend
RESEND_API_KEY=

# Add only for Amazon SES
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=
SES_FROM_EMAIL=

# Add only for the doubt solver
GEMINI_API_KEY=
```

The real `.env` file must be ignored by Git. Only `.env.example` will be committed.

## 10. Information I need from you

You do **not** need to send passwords, card information, database URLs, or API secret keys to me.

Please provide these non-secret decisions:

1. The final sender name, recommended: `Abhyaas`.
2. The sender email you want users to see.
3. Whether you own a domain name. If yes, provide only the domain name.
4. Email choice:
   - `Resend free` — recommended for a long-term ₹0 launch.
   - `AWS SES Free Plan` — your requested option, but temporary for up to six months.
5. Login email choice:
   - New-device login alerts only — recommended.
   - An email after every login.
6. Whether users must verify their email before using the platform.
7. Official CDS content/PDF sources that you want included first.
8. Whether the GitHub repository will be public or private.

## 11. ₹0 launch checklist

- [ ] No paid plan has been selected.
- [ ] No automatic paid upgrade is enabled.
- [ ] Every service limit is recorded.
- [ ] API endpoints have per-user rate limits.
- [ ] Gemini calls have a daily cap.
- [ ] Email sends have a daily cap.
- [ ] Render has no payment method, or a strict spend limit where available.
- [ ] Neon remains on its Free plan.
- [ ] Vercel remains on Hobby and the site remains non-commercial.
- [ ] AWS remains on the Free Plan and has an expiry reminder, if SES is used.
- [ ] All secrets are stored only in environment settings.
- [ ] Database backups/exports are downloaded periodically.

## 12. Official pricing and setup references

- [AWS Free Tier](https://aws.amazon.com/free/)
- [AWS Free Tier FAQs](https://aws.amazon.com/free/free-tier-faqs/)
- [Amazon SES pricing](https://aws.amazon.com/ses/pricing/)
- [Moving Amazon SES out of the sandbox](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html)
- [Resend pricing](https://resend.com/pricing)
- [Neon pricing](https://neon.com/pricing)
- [Render free service limitations](https://render.com/docs/free)
- [Vercel Hobby plan](https://vercel.com/docs/plans/hobby)
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Cloudflare R2 pricing, if storage is needed later](https://developers.cloudflare.com/r2/pricing/)

## 13. First implementation milestone

The first backend milestone should contain only:

1. FastAPI foundation.
2. Neon connection and migrations.
3. Signup, login, logout, refresh, and current-user endpoints.
4. Email verification using a provider interface.
5. Console email provider for completely free local development.
6. Existing frontend login/signup connected to the API.
7. Automated authentication tests.

Practice, PDFs, and AI should start only after this authentication milestone is stable.
