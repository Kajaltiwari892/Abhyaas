# Abhyaas

**Less searching. More preparation.**

A focused study space for CDS aspirants: practise questions, solve previous papers, clear doubts, and track progress in one place.

[Explore Abhyaas](https://abhyaas-two.vercel.app) · [How it works](#how-it-works) · [Local setup](#run-locally)

## Why Abhyaas?

**Study material is everywhere. A clear path through it is not.**

A concept is in one resource, its questions are in a PDF, and the explanation is somewhere else.

Abhyaas connects them: **learn a topic, practise it, clear your doubts, and review your progress** without switching between scattered resources.

## What you can do

- **Focused practice:** choose your subject, topic, set size, and academy target.
- **Previous papers:** solve source-linked questions and resume saved attempts.
- **AI doubt solver:** ask questions, paste question images, and reopen past chats.
- **Results and progress:** review complete sets, skipped questions, and practice history.
- **A personal study space:** manage study memory and meet an animated 3D companion.

## How it works

The doubt solver uses different paths for different requests:

1. **Actual exam questions** come from stored paper records, with the original source linked.
2. **Concept explanations** use RAG: the system finds relevant study passages and gives them to the AI as reference material. Available sources are shown with the answer.
3. **New practice questions** are generated separately and labelled as AI practice—not official PYQs.

Qdrant searches study passages by meaning using *embeddings*. If vector search is unavailable, the system falls back to database keyword search.

PostgreSQL saves questions, accounts, attempts, and chats. Study memory personalises replies; it does not retrain the AI.

**AI explanations never replace official answer keys.** Generated practice is labelled separately. Paper coverage is growing, and AI answers can make mistakes.

[Read the RAG architecture](Backend/RAG_ARCHITECTURE.md) · [Question retrieval and companion](Backend/PYQ_AND_COMPANION_GUIDE.md)

## Built with

| Part | Tools |
| --- | --- |
| Website | Next.js, React, TypeScript, Tailwind CSS, CSS Modules |
| Backend | FastAPI, Pydantic, SQLAlchemy |
| Data and search | PostgreSQL, Alembic, Qdrant |
| AI | Google Gemini for explanations, embeddings, and image questions |
| Interaction | Three.js companion, Motion animations, Recharts progress charts |
| Testing and hosting | Pytest, Node tests, ESLint, TypeScript, Vercel |

## Run locally

You need **Python 3.12+**, **Node.js 24**, and **PostgreSQL**. AI features also need a Gemini API key.

1. Follow the [backend setup](Backend/README.md#manual-setup-reference) to configure the database and start the API.
2. In `Frontend/abhyaas`, copy `.env.example` to `.env.local` if you don't already have one. Run `npm ci`, then `npm run dev`.
3. Open [localhost:3000](http://localhost:3000).

Configuration templates: [backend](Backend/.env.example) · [frontend](Frontend/abhyaas/.env.example). Never commit real credentials.

Deploying? Follow the [deployment guide](VERCEL_DEPLOYMENT.md) and update both frontend and backend.

## What's next

Planned: daily practice missions, a personal mistake notebook, and scheduled revision.

---

Abhyaas is an independent project, not an official UPSC service. Original papers belong to their respective owners.
