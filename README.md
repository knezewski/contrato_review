# Contrato Review

A service for preliminary review of residential sale (compraventa) and lease (locación) contracts in the City of
Buenos Aires (CABA), written in Spanish. The user uploads a PDF or DOCX file. The service splits the contract into clauses,
finds the applicable norms in a knowledge base, analyzes each clause with a generative model, and returns a report: risks,
mismatches, gaps in mandatory elements, and an estimate of the CABA stamp tax (impuesto de sellos).

> **Important.** The report is informational. Only the original Spanish text is legally binding. The final decision
> is made by a qualified lawyer.

Phase 0 (MVP). The specification, plan, and task list are in [`specs/001-contract-review-mvp/`](specs/001-contract-review-mvp/).
Project rules are in [`.specify/memory/constitution.md`](.specify/memory/constitution.md).

## What the service does

- Extracts text from PDF (PyMuPDF) and DOCX (python-docx). Scans without a text layer are processed only if OCR is
  enabled; otherwise a clear error is returned.
- Splits the contract into clauses by the markers `CLÁUSULA` / `ARTÍCULO`, and by numbering only when there are no legal markers.
  The text before the first marker is kept separately as the preamble.
- Detects the contract type (compraventa / locación) and the signing date. If the date cannot be found, the service returns
  422 and asks for it in the `signing_date` field.
- Selects one legal regime for the whole contract by signing date: DNU 70/2023 for 30 December 2023 and later, Ley 27.551
  before that. The dates come from the norms knowledge base, not from the code.
- For each clause, searches for norms (only `nacional` and `CABA`) with vector search over embeddings, and sends one clause
  together with the norms found for it to the model.
- Checks the mandatory elements of the contract (price, term, and so on) deterministically, with no external calls.
  A missing element is reported as a gap for manual review.
- Estimates the CABA stamp tax (impuesto de sellos): for a sale, the amount when all the data is available; for a lease,
  only whether the tax applies and who pays it. The rate is marked `pending`.
- Stores the report on the server for 30 days, retrievable by `report_id`, in Spanish, English, or Russian.
  The contract text is not stored, and the uploaded file is deleted right after the review.

## What it does not do

- It does not give legal opinions and does not replace a lawyer.
- It works only with CABA and only with sale and residential lease contracts.
- It does not recognize scans unless OCR is enabled.
- It has no authentication: run it only in a local or pilot environment.

## Stack

Python 3.11, FastAPI, Uvicorn, Pydantic v2, ChromaDB (local, collection `ar_law`, cosine metric),
`intfloat/multilingual-e5-large` (embeddings, run locally), Anthropic Claude (analysis and translation).
Tests use pytest, coverage uses pytest-cov, and the linter is ruff.

## Quick start

Requires Python 3.11.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env          # fill in ANTHROPIC_API_KEY, and HF_TOKEN if needed
```

Build the norm index (the first run downloads the embedding model, about 2.2 GB):

```bash
python -m src.kb.index build --laws data/laws --reset
python -m src.kb.index check  # check query: prints the norms found and their scores
```

Start the service:

```bash
uvicorn src.api.app:app --reload --port 8000
curl -s localhost:8000/v1/health
```

Review a contract (the file must be synthetic or anonymized):

```bash
curl -s -F "file=@contrato.docx" -F "lang=en" localhost:8000/v1/reviews
```

## API

| Method and path | What it does |
|-----------------|--------------|
| `POST /v1/reviews` | Uploads a file (`file`), with optional `signing_date` (YYYY-MM-DD) and `lang` (`es`, `en`, `ru`). Returns `report_id`, the retention period, the report in Spanish, and the report in the selected language |
| `GET /v1/reports/{report_id}?lang=es` | A stored report in the requested language. The analysis is not re-run. An expired id and an unknown id give the same 404 |
| `GET /v1/health` | Service status: number of norms in the index, embedding model, number of stored reports |

All errors use one format:

```json
{"error": {"code": "SIGNING_DATE_REQUIRED", "message": "...", "message_en": "...", "request_id": "..."}}
```

Main codes: `UNSUPPORTED_FORMAT` (415), `FILE_TOO_LARGE` (413), `DOCUMENT_UNREADABLE`, `OCR_UNAVAILABLE`,
`NO_CLAUSES_DETECTED`, `CONTRACT_TYPE_UNDETECTED`, `SIGNING_DATE_REQUIRED`, `SIGNING_DATE_INVALID`,
`LANG_UNSUPPORTED` (422), `LLM_UNAVAILABLE` (503), `LLM_INVALID_OUTPUT` (502), `REPORT_STORE_FAILED` (500).
When an error occurs, no report is returned: there are no partial reports.

Full contracts are in [`specs/001-contract-review-mvp/contracts/api.md`](specs/001-contract-review-mvp/contracts/api.md).

## Configuration

Values are read from the environment and from `.env`. The full list and the defaults are in `src/config.py`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | — | Provider key. Without it, analysis returns 503 |
| `LLM_MODEL` | `claude-sonnet-5-5` | Model for analysis and translation |
| `LLM_MAX_ATTEMPTS` | `3` | Attempts per clause (including the first) |
| `LLM_CONCURRENCY` | `5` | Clauses processed in parallel |
| `RETRIEVAL_K` | `5` | Norms per clause |
| `CONFIDENCE_THRESHOLD` | `0.3` | A clause below this score is marked for manual review |
| `EMBED_MODEL` | `intfloat/multilingual-e5-large` | Embedding model |
| `CHROMA_PATH` / `CHROMA_COLLECTION` | `data/chroma` / `ar_law` | Norm index |
| `REPORTS_DB_PATH` | `data/reports.db` | SQLite database with reports |
| `REPORT_RETENTION_DAYS` | `30` | Report retention period |
| `MAX_UPLOAD_MB` | `10` | File size limit |
| `OCR_ENABLED` / `OCR_LANG` | `false` / `spa` | OCR for scans; needs the system `tesseract` with the `spa` language |

Secrets (`ANTHROPIC_API_KEY`, `HF_TOKEN`) are kept only in `.env`, which is not committed to git.

## Knowledge base

Norms are in `data/laws/` as JSON files with lists of records. Each record must have `article`, `regime`,
`jurisdiction`, `contract_type`, `valid_from`, `source_url`, and `text`. An open validity period is `valid_to: null`.

| File | Content | Status |
|------|---------|--------|
| `nacional/ccyc_locacion.json` | CCyC norms 1198 and 1221 for leases, in two versions: Ley 27.551 and DNU 70/2023 | The DNU 70/2023 version is a paraphrase (`verbatim: false`) and needs checking against the decree text |
| `nacional/ccyc_compraventa.json` | Empty | Sale norms are not in the KB. They must come from the primary source (see "Limitations") |
| `nacional/required_elements.json` | Empty | Patterns for mandatory elements await checking against the primary source |
| `caba/codigo_fiscal_sellos.json` | CABA stamp tax under Ley Tarifaria 2026: sale of a residence and of other property; lease is `pending` | The texts are paraphrases; check them against the literal annex text before production use |

Records enter the index only through `python -m src.kb.index build`. A norm ID is `{regime}-{article}`, so two records
with the same regime and article are a data error.

## Tests

```bash
pytest tests/unit tests/contract --cov=src        # as in CI
pytest tests -m "integration"                     # retrieval on the real index; needs the model
```

- `tests/unit/` — modules tested with fakes (model, embedder) and on synthetic files.
- `tests/contract/` — the HTTP contract through `TestClient` on the real index; the analysis model is replaced.
- `tests/integration/` — norm search on the real index.
- `tests/fixtures/` — synthetic contracts. To regenerate: `python tests/fixtures/make_fixtures.py`.
  The tests contain no personal data, and this is mandatory.

One test is marked `xfail`: sale norms are missing from the knowledge base. When they are added, remove the `xfail`.

Lint and format: `ruff check src tests` and `ruff format --check src tests`.

## CI

`.github/workflows/ci.yml` runs the unit and contract tests with coverage and uploads the report to Codecov and Code Climate.
The service configs are `codecov.yml` and `.codeclimate.yml`. The embedding model is cached between runs.
The `CODECOV_TOKEN` and `CC_TEST_REPORTER_ID` tokens are set in the repository settings.

## Repository layout

```
src/
  ingest/      text extraction, clause splitting, contract type and date, OCR fallback
  kb/          embedder, dates as YYYYMMDD, Chroma index, KB reads
  retrieval/   norm search with filters on jurisdiction, regime, and period
  review/      regime selection, clause analysis, gaps, CABA taxes, pipeline, model client
  report/      report models, translation, disclaimer and labels
  store/       report storage (SQLite, 30 days)
  api/         FastAPI: routes, errors, dependencies, logging
data/          norms, glossary, index and reports (generated, not in git)
tests/         unit, contract, integration, fixtures
specs/         specification, plan, tasks, and contracts (Spec Kit)
```

## Limitations and open questions

- **Sales without norms.** The knowledge base has no CCyC norms for sales and no regimes for them. So for sale contracts
  `regime` is empty, and the report says so. Norms may be added only from the primary source.
- **Gaps are not reported yet.** `required_elements.json` is empty. Until the patterns are checked, the check reports nothing.
- **The 0.3 confidence threshold is provisional.** Scores on the synthetic base are now 0.8–0.9; the threshold will be
  tuned after runs on real contracts.
- **No authentication.** The service is not meant for open access. `report_id` is the only protection of a report.
- **Model provider.** Before the first real contract, the data-retention and training terms at Anthropic must be checked and
  recorded (a constitution condition, principle V).
- **Progress indicator (AC9)** is not implemented: the format decision has not been made yet.
- **Performance.** The target "95% of contracts of up to 10 clauses in under 60 seconds" has not been measured: a real model key is needed.

The full task list and execution notes are in [`specs/001-contract-review-mvp/tasks.md`](specs/001-contract-review-mvp/tasks.md).
