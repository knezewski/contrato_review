# Quickstart: end-to-end validation of Contract Review MVP

The scenario shows the feature works: the index is built, regime selection by date works, the report is produced with the
disclaimer, and errors are returned without partial reports. Contracts — [contracts/api.md](./contracts/api.md),
entities — [data-model.md](./data-model.md).

## Prerequisites

- Python 3.11, project `.venv` (`source .venv/bin/activate`).
- Dependencies installed from the pinned `requirements.txt`.
- `.env` with `ANTHROPIC_API_KEY` (not committed, not copied into tests).
- The embedding model `intfloat/multilingual-e5-large` downloaded (the first run fetches it from Hugging Face).
- For the optional OCR check: system `tesseract` with the `spa` language, `OCR_ENABLED=true`.

## 1. Build the norm index

```bash
python -m src.kb.index build --laws data/laws
python -m src.kb.index check
```

Expected: `records > 0`; `check` returns, for the query "plazo mínimo locación", records `1198` for both regimes with different
periods (`Ley 27.551` up to 2023-12-29, `DNU 70/2023` from 2023-12-30). All `valid_from_i`/`valid_to_i` are int;
an open `valid_to` → `99991231`. If `index` fails on a `null`/empty date, that is the expected guard (R4).

## 2. Start the service

```bash
uvicorn src.api.app:app --reload --port 8000
curl -s localhost:8000/v1/health
```

Expected: `"status": "ok"`, and `kb_records` matches step 1.

## 3. Run on a synthetic contract

Use only synthetic contracts (constitution V): `tests/fixtures/locacion_2026_synthetic.docx`
(clauses CLÁUSULA PRIMERA…, signing date "a los 15 días del mes de marzo de 2026").

```bash
curl -s -F "file=@tests/fixtures/locacion_2026_synthetic.docx" -F "lang=en" \
     localhost:8000/v1/reviews | jq '.report.contract_type, .report.signing_date, .report.regime'
```

Expected:
- `contract_type = "locacion"`, `signing_date = "2026-03-15"`;
- `regime.regime = "DNU 70/2023"` (UC1);
- `rendered.disclaimer` contains the three AC11 statements in English; `report` is in Spanish.

Repeat with `tests/fixtures/locacion_2022_synthetic.docx` → `regime = "Ley 27.551"` (UC2).

Gap check (AC17): `tests/fixtures/locacion_no_price_synthetic.docx` (the text has no price or term signs) →
`report.contract_gaps` contains a `Finding` with `type = "gap"`, `source = "heuristic"`, `needs_manual_review = true`,
`article_refs` with exactly one `required_element`, and a non-empty `searched_patterns`. No LLM calls are made for this step.

## 4. Date not found → request the date

A file without a signing date (`tests/fixtures/no_date_synthetic.docx`):

```bash
curl -s -F "file=@tests/fixtures/no_date_synthetic.docx" localhost:8000/v1/reviews | jq .error.code
# "SIGNING_DATE_REQUIRED"
curl -s -F "file=@tests/fixtures/no_date_synthetic.docx" -F "signing_date=2025-06-01" \
     localhost:8000/v1/reviews | jq .report.regime.regime
# "DNU 70/2023"
```

## 5. Errors without partial reports

```bash
curl -s -F "file=@tests/fixtures/scan_no_text_synthetic.pdf" localhost:8000/v1/reviews | jq .error.code
# "OCR_UNAVAILABLE" when OCR_ENABLED=false
curl -s -F "file=@README.md" localhost:8000/v1/reviews -o /dev/null -w "%{http_code}\n"
# 415
```

AC14 check: temporarily set an invalid `ANTHROPIC_API_KEY` and run step 3 → HTTP 503 `LLM_UNAVAILABLE`,
and the body has no `report` field.

## 6. Get a stored report in another language

```bash
ID=$(curl -s -F 'file=@tests/fixtures/locacion_2026_synthetic.docx' localhost:8000/v1/reviews | jq -r .report_id)
curl -s "localhost:8000/v1/reports/$ID?lang=ru" | jq '.disclaimer, .legal_terms'
```

Expected: the disclaimer is present in Russian; the terms in brackets keep the Spanish original
(for example, `locación (аренда)`). A repeat request with `lang=es` does not call the LLM (check the log: no provider call).

## 6a. Retention period

```bash
curl -s -o /dev/null -w "%{http_code}\n" "localhost:8000/v1/reports/00000000-0000-4000-8000-000000000000"
# 404
```

AC15 check: in a test environment, set `REPORT_RETENTION_DAYS` to a small value (or move `expires_at` in the database),
wait for expiry, and repeat the request for the stored `report_id` → 404 `REPORT_NOT_FOUND`, with the same body and status
as for an unknown id.

## 7. Privacy check

- During the step 3 run, the logs (`uvicorn` stdout) contain no lines from the contract text (grep for a clause fragment → nothing).
- No new files containing contract content appear in the project directory after the request (`data/` gets no new files,
  except `data/chroma` after re-indexing and `data/reports.db`).
- `data/reports.db` contains no contract text: `sqlite3 data/reports.db "select report_json from reports" | grep -c "<clause fragment>"` → 0.

## 8. Tests

```bash
pytest tests/unit -q
pytest tests/contract -q        # HTTP contracts, fake LLM
pytest tests/integration -q     # retrieval on the real index, needs step 1
```

Acceptance: all three sets are green; step 3 finishes in under 60 s for a 10-clause synthetic contract
(measured by the `duration_ms` field in the run's log line, see R13).

Note: the fixtures used in steps 3–5 do not exist in the repository yet; they must be created synthetically as part of the tasks
(`tests/fixtures/`), without real personal data.
