# Feeding previous-paper data

Only add questions copied from the official UPSC paper. Every answer and explanation must be
checked by a person before import; the importer deliberately rejects questions unless
`is_verified` is `true`.

1. Copy `paper-template.json` and rename it, for example `cds-ii-2024-english.json`.
2. Fill the paper metadata and questions. `correct_index` is zero-based: `0` means option A.
3. Keep the official UPSC PDF in `source_url`. Add `answer_key_url` only when an official key
   exists.
4. Review every question, answer, formula and explanation.
5. From the `Backend` folder, run:

   ```powershell
   .\.venv\Scripts\python.exe .\scripts\import_papers.py .\data\papers\your-file.json
   ```

Running the same file again updates existing question numbers instead of creating duplicates.
Do not commit downloaded PDFs; retain the official URL and checksum in the JSON instead.
