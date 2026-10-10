# Feeding previous-paper data

## Chapter-wise PYQs

The first Sound and Waves release is `data/chapter_questions/sound-waves-20261009.json`.
It contains six source-compared questions from CDS I/II 2023, CDS II 2025 and CDS I 2026,
not an exhaustive historical archive. Migration `20261009_26` adds four questions and
improves two existing questions' tags. It keeps question IDs, checked answers and student
history. Chapter collections do not mean the rest of an older paper is transcribed.

Questions live in the existing `paper_questions` table, linked to `previous_papers`.
Their transcription stores chapter/subtopic tags, source page and review checksum.
PYQ search counts all matches, shows up to 50 per reply and continues with "Show next
PYQs". PDF-only papers are included in the coverage denominator. Seismic waves and
optics are not included just because their wording mentions waves or frequency.

To expand the collection, use a new dated release filename:

```powershell
.\.venv\Scripts\python.exe scripts/collect_chapter_candidates.py --years 2022 2023 --ocr --max-papers 4 --output ../tmp/pdfs/chapter-review/candidates.json
.\.venv\Scripts\python.exe scripts/export_chapter_questions.py ../tmp/pdfs/chapter-review/reviewed-draft.json --output data/chapter_questions/sound-waves-YYYYMMDD.json
.\.venv\Scripts\python.exe scripts/import_chapter_questions.py data/chapter_questions/sound-waves-YYYYMMDD.json
```

The collector uses no AI API and does not write to the database. OCR snippets are drafts;
compare every included question, choice, number and unit visually with the original PDF.
Unscanned/unreadable pages remain pending. `--pages` plus `--render-only` can prepare a
bounded visual-review batch when OCR is slow. A draft uses the versioned release schema;
the exporter computes question checksums and renders source images, but cannot perform
the source comparison for you. It refuses to replace an existing release bundle.

The importer is a dry run unless `--apply` is supplied. It rejects changed PDFs/text and
never writes answers or student data. Publish a new release via an additive migration
so the live database receives the same public data on deployment. Do not copy local
accounts or histories to production. Full-paper publication can later fill remaining
questions while preserving this collection's existing IDs and reviewed text.

## Official PDF archive

Migration `20261001_18` publishes the reviewed public manifest
`data/upsc_paper_archive_20261001.json`. It adds missing papers only; existing paper IDs,
questions, answer keys, and student attempts are not replaced.

The checked snapshot contains 63 PDFs: CDS I and II for 2017–2026, plus CDS II 2016,
in English, General Knowledge, and Elementary Mathematics. UPSC's current and archived
listings do not include CDS I 2016 or earlier years. Do not describe this as an all-time archive.
These new entries are PDF-only until their questions are separately transcribed and reviewed.
An unknown exact exam date remains null rather than using an invented date.

To discover a future snapshot, run from `Backend` with a **new** dated output filename:

```powershell
.\.venv\Scripts\python.exe scripts/discover_official_paper_archive.py --output data/upsc_paper_archive_YYYYMMDD.json
```

The script reads both official listings, requires all three subjects per sitting, and checks
each official URL for a PDF signature using small streamed requests. Review the manifest,
then publish it in a new insert-only migration; do not overwrite an already-released snapshot.
The frontend derives year options from the catalogue, so new years need no hard-coded UI change.

## Interactive questions

### Converting the older archive

The resumable authoring commands below read only public UPSC PDFs. They never read student
data or modify the database. They use the configured Gemini account and its usage quota.

```powershell
.\.venv\Scripts\python.exe scripts/transcribe_archive_papers.py --folder cds-ii-2024/english --max-calls 16
.\.venv\Scripts\python.exe scripts/review_archive_pages.py --folder cds-ii-2024/english --max-calls 45
.\.venv\Scripts\python.exe scripts/export_interactive_archive.py --folder cds-ii-2024/english --output data/interactive_archive_NEW_RELEASE.json
```

Drafts, source PDFs, and page-comparison checkpoints live in ignored
`tmp/pdfs/archive-authoring/`. Export refuses incomplete question sets or pages that have
not received a separate source-image comparison. Compare representative and difficult
questions visually before publishing; a complete number count does not prove correct text.
The source comparison remains AI-assisted, not a claim of human verification.

`app.services.archive_publication.publish()` inserts complete paper questions inside a
caller-owned transaction and refuses to overwrite existing questions. Publish a reviewed
bundle through a new release migration; do not enable Solve by adding empty placeholder rows.
Transcription does not create answer keys. Unverified answers stay excluded from scoring.

The authoring runner stops when the provider reports a daily quota. Do not loop retries or
silently switch accounts to work around it. Resume after quota resets or the account owner
changes their quota/billing; successful batches are retained.

Only add questions from the official UPSC paper. The archive can contain an official question
before its answer has been verified, but it must include the exact source scan in `asset_url`.
Unverified questions use `is_verified: false` and omit `correct_index` and `explanation`.

1. Copy `paper-template.json` and rename it, for example `cds-ii-2024-english.json`.
2. Fill the paper metadata and questions. For a verified answer, `correct_index` is zero-based:
   `0` means option A.
3. Keep the official UPSC PDF in `source_url`. Add `answer_key_url` only when an official key
   exists.
4. Check every question image against the official PDF. Set `is_verified: true` only after the
   answer and explanation have also been independently checked.
5. From the `Backend` folder, run:

   ```powershell
   .\.venv\Scripts\python.exe .\scripts\import_papers.py .\data\papers\your-file.json
   ```

Running the same file again updates existing question numbers instead of creating duplicates.
Do not commit downloaded PDFs. Keep the official URL and checksum, and commit only optimized
question/page images needed by the student-facing viewer.

For image-only UPSC scans, create one-question viewports with the OCR authoring utility:

```powershell
.\.venv\Scripts\python.exe .\scripts\extract_paper_crops.py --folder cds-i-2026/english
```

Install `rapidocr-onnxruntime` in the backend virtual environment before running it. The command
will refuse to silently publish a page when any expected question number cannot be located.
