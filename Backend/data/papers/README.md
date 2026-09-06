# Feeding previous-paper data

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
