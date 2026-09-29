# Abhyaas doubt-solver architecture

The doubt solver uses retrieval-augmented generation (RAG). PostgreSQL is the system of record,
Qdrant is the vector index, Gemini Embedding 2 creates 768-dimensional embeddings, and a Gemini
Flash model writes an answer with relevant retrieved passages. General academic reasoning is allowed
and labelled separately from source-backed answers; this is not a source-only chatbot.

```text
approved PDF/text
      │
      ▼
PostgreSQL documents + page-aware chunks ──► Gemini embeddings ──► Qdrant
                                                                    │
student question ──► query embedding ──► subject filter + cosine search
                                                                    │
                                                                    ▼
saved conversation ◄── cited answer ◄── Gemini constrained to retrieved evidence
```

## Runtime request

Actual PYQ listing now takes a separate deterministic route: source-linked transcriptions in
`paper_questions` are filtered and returned as structured cards without asking Gemini to write
question text. Saved `pyq_result` metadata supports owner-scoped year/chapter follow-ups. Generated
practice is explicitly labelled and never mixed into those cards. Archive lists default to ten records,
honor explicit counts up to 50, and retain pagination/full indexed-match counts for larger collections.
Focus filters inspect question text inside broad chapter tags. See `PYQ_AND_COMPANION_GUIDE.md`.

Generic question-set requests take a third route: `practice_sets.py` generates structured practice,
up to 50 MCQs in one primary call. A JSON schema constrains exact cardinality and field types. Local
validation checks option count/uniqueness, answer index, types and lengths. Normalized duplicate prompts are
removed, and up to two bounded 25-item repair calls can fill a shortfall. Partial sets disclose their actual count;
failed generation never manufactures provenance. `practice_result` is saved separately from `pyq_result`.
Ordinary lessons and solves continue through the tutor route, not the archive-listing route.

1. Bounded middleware accepts at most 6 MiB of JSON, including chunked bodies, before parsing.
2. `POST /api/v1/doubts/ask` authenticates the student and uses PostgreSQL row locks to enforce
   ownership, one active question per account, four attempts per minute and the daily limit (30).
3. Optional question images are validated and normalized in memory. Gemini transcribes the question
   before retrieval; textbook passages, notes and labelled diagrams are accepted too. The normalized
   image also accompanies answer generation. Unreadable content is never filled in by guessing.
4. Relevant paper-catalog entries and Qdrant passages are retrieved. Vector work has an eight-second
   budget; failures fall back to lexical matching over active PostgreSQL sources.
5. Gemini receives evidence with stable IDs (`S1`, etc.), up to six recent messages and the student's
   study preferences. It can explain academic concepts and solve visible maths/grammar questions
   without a matching source, but must not invent official papers, answer keys or unreadable details.
6. Returned source IDs are checked against the retrieved set. Uncited explanations are labelled as
   AI explanations and confidence is capped at 0.6, not presented as a verified official answer.
7. Successful question text, recognized image text, answers and citations are saved in PostgreSQL.
   Academic topic counts update only when memory is enabled. Raw images are never stored by Abhyaas.

Conversation access is owner-scoped. Failed AI calls are rolled back and do not consume the
student's daily allowance.

If weak retrieval causes the sourced model to refuse an ordinary academic explanation, the service
retries once in clearly labelled general-tutor mode, without carrying that refusal into its history.
This recovery does not apply to official papers, answer keys, cutoffs or time-sensitive exam facts.
Those still require evidence; general AI knowledge is not a substitute for an official source.

Generation reuses a working provider model rather than retrying a failing preferred model on every
image-reading and answer call. Each attempt has bounded connection/read timeouts. AI processing is
limited to 75 seconds for ordinary requests, or 150 seconds for bulk sets/all-results requests
(including replies to a pending bulk-topic clarification). Account leases are respectively 90 or 165
seconds. Failed requests release the lease. Failed attempts still count toward burst
limits. Official-evidence requests can show clearly labelled retrieved excerpts when generation is
unavailable; ordinary lessons and image solves return a retryable error instead of presenting unrelated
paper excerpts as a solution. Negated paper intent does not trigger paper-catalog retrieval.

Practice output budgets scale from 8192 to at most 24576 tokens. A large primary set has a 95-second
provider read timeout; smaller/repair sets allow 45 seconds. Gemini 3 uses low thinking level for practice
and its default temperature, while 2.5 Flash uses a 1024-token thinking budget. Thought parts are excluded
from JSON parsing and truncated output is rejected. The configured model falls back to
`GEMINI_FALLBACK_MODEL` (default `gemini-3.5-flash-lite`), then legacy 2.5 Flash. The working model is
reused. Per-worker model cooldowns suppress immediate retries after throttling/outages; one short retry
is allowed for connection failures, not for 429 responses. This is not a distributed quota manager.
The primary batch phase is bounded to 110 seconds for bulk sets; repair shares an overall 140-second
generation window, leaving room for API cleanup. These limits bound work but do not guarantee
provider availability. See Google's [thinking configuration documentation](https://ai.google.dev/gemini-api/docs/generate-content/thinking).

## Image safety

- One JPG, PNG or WebP, maximum 4 MiB, 12 megapixels and 6000 pixels per side; minimum 16 pixels.
- Validate actual format against MIME type. Reject corrupt files, animations and oversized images.
- Check dimensions before decoding, apply EXIF orientation, flatten transparency, resize to at most
  1800 x 1800, then re-encode to JPEG without original metadata. Nothing is written to image storage.
- At most four in-flight uploads/answers per application worker and a 15-second upload deadline.
- Image text is treated as untrusted question data, not system instructions. This prompt safeguard
  is not a guarantee against all prompt-injection attempts.

Production still needs ingress body/connection limits, IP-based abuse protection and provider spend
limits. Per-worker admission control alone is not a distributed DDoS defence.
Any reverse proxy serving bulk generation must allow the API's 150-second processing window plus
transport overhead. A deployment with shorter function/proxy limits needs background jobs and polling
or streaming rather than relying on this synchronous development endpoint.

## Personalization, not model training

`doubt_study_profiles` is keyed by the authenticated user's ID. It stores counts from a fixed academic
taxonomy, the chosen explanation style and request-limit state. It does not infer personal traits or
diagnose mastery. Topics affect starter suggestions and relevant examples; style affects future chats.

`GET`, `PATCH` and `DELETE /api/v1/doubts/personalization` expose the owner's profile, pause/style
controls and memory reset. Reset preserves rate limits and existing chat history; paused memory is
neither updated nor included in new prompts. Old chats are not automatically backfilled.

This does not update model weights or fine-tune a shared model. Actual training would need a separate
consent/data policy, curated examples, evaluations and a training pipeline. Images, question text and
relevant preferences go to the AI provider under its own service/data terms.

## Source ingestion

Migrations seed a small verified starter corpus. To add an approved source:

```powershell
python scripts/ingest_knowledge.py source.pdf `
  --title "Source title" `
  --publisher "Publisher" `
  --subject general-knowledge `
  --source-url "https://official.example/source"
```

PDF ingestion is page-aware and requires the `rag-authoring` optional dependency. Text and Markdown
work without it. Checksums prevent duplicates and changed chunks are automatically re-embedded.

## Deployment

Install the backend dependencies (including Pillow) and run `alembic upgrade head` for migration
`20260929_15` (including the earlier question-bank migration) and run
`python scripts/import_question_bank.py --apply` before deploying the new UI.
For larger reference corpora, run `python scripts/sync_knowledge.py`
outside request handling; the eight-second request-time budget intentionally falls back during a
slow rebuild instead of blocking the tutor.

Development uses Qdrant's persistent local mode at `QDRANT_LOCAL_PATH`. Production deliberately
requires `QDRANT_URL` (and `QDRANT_API_KEY` when the provider requires it), because serverless local
filesystems are ephemeral. The same application code works with Qdrant Cloud or a self-hosted
Qdrant server.
