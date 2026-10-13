# Implementation Plan: Contract Review MVP (CABA, Phase 0)

**Branch**: `001-contract-review-mvp` | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-contract-review-mvp/spec.md`

## Summary

A FastAPI REST service: the user uploads a contract (PDF/DOCX, Spanish). The service extracts the text,
splits it into clauses by legal markers, determines the contract type and signing date, selects one legal
regime for the whole contract by signing date, runs a RAG search for norms for each clause
(jurisdiction ∈ {nacional, CABA}) in Chroma, and sends one clause together with the norms found for it to a
generative LLM. The LLM returns a structured analysis in Spanish. The result is assembled into a
language-neutral report; translation to EN/RU is a separate output layer. The language-neutral report is kept
on the server for 30 days (by `report_id`) and then deleted. The contract text is not stored and is deleted
right after the report is generated.

Technical approach and decisions are in [research.md](./research.md); entities and report structure are in
[data-model.md](./data-model.md); HTTP contracts are in [contracts/api.md](./contracts/api.md); the validation
scenario is in [quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.11 (project `.venv`)

**Primary Dependencies**: FastAPI, Uvicorn, pydantic v2 + pydantic-settings, PyMuPDF (`fitz`), python-docx,
chromadb (PersistentClient), sentence-transformers (`intfloat/multilingual-e5-large`), anthropic SDK
(LLM provider, see research.md R3), httpx (API tests). OCR (`pytesseract`, `pdf2image`, system `tesseract`) —
optional, not a required dependency.

**Storage**: Chroma PersistentClient in `data/chroma`, collection `ar_law`, `hnsw:space=cosine`. Source norms —
JSON in `data/laws/`. Contracts are not stored (only in process memory for the duration of a request). Reports —
SQLite `data/reports.db` (table `reports`, fields `report_id`, `created_at`, `expires_at`, `report_json`), retention
30 days, expired records purged (R14). Production: pgvector for norms (out of MVP scope, see R2).

**Testing**: pytest, pytest-asyncio, httpx `AsyncClient` for the API; the LLM and embedder are replaced with fakes in
unit tests; a separate run of check queries (`check` stage) on the real index. Coverage is measured with `pytest-cov`
(`coverage.xml` format) and sent to Codecov (see "Code quality and coverage" below).

**Quality tooling (CI, not runtime dependencies)**: Codecov — test coverage and finding uncovered places; Code Climate —
code analysis for improvements (complexity, duplication, style via engines). These are external cloud services, not
libraries: the project adds only `pytest-cov` and the service configuration; tokens live in CI secrets, not in `.env`
or the repository.

**Target Platform**: Linux/macOS, one Uvicorn process; local development and one server (MVP).

**Project Type**: web-service (REST API).

**Performance Goals**: for contracts of up to 10 clauses, 95% of runs finish in under 60 s (spec §4). Clauses are
processed in parallel (concurrency limit, see config).

**Constraints**:
- Embeddings and retrieval are local; contract text goes to the external LLM (Anthropic) only one clause at a time together with its norms.
- The mandatory-element (gap) check is deterministic: KB patterns over the whole contract text, no external calls.
- Contract text is not stored after the report is generated and does not reach the logs; the report (without contract text) is kept for 30 days.
- All date filters use int `YYYYMMDD`; an open `valid_to` is `99991231`.
- No partial reports: any unrecoverable error → HTTP error without a report body.

**Scale/Scope**: MVP for a single operator/pilot user; contracts of up to ~10–30 clauses; the KB has dozens of norms
(CCyC locación/compraventa + DNU 70/2023 + Ley 27.551 + CABA sellos).

## Constitution Check

*GATE: checked before Phase 0 and again after Phase 1 (constitution v2.0.0).*

| Principle | Check | Status |
|-----------|-------|--------|
| I. Source-Grounded Legal Claims | Every `Finding` that reports a problem must have `article_refs` that are a subset of the norms actually returned by retrieval for that clause. Otherwise `no_norm_found=true`. Validator in data-model. `verbatim: true` is quoted verbatim (the `text` field unchanged). | PASS (by design) |
| II. Temporal Validity of Law | Regime and date filter: `valid_from_i <= D <= valid_to_i`, where `valid_to_i = 99991231` for open records. **Gap with current data**: in `data/laws/*.json` an open `valid_to` is `null` and dates are ISO strings. Normalization to int is required in the `index` ingestion stage (see the task on research R4). | PASS with a condition |
| III. Advisory Output, Human Decision | The disclaimer (AC11) is fixed text in every report in all languages; uncertainty (`needs_manual_review`) is shown explicitly. Heuristic findings (gaps, `source = "heuristic"`) are labeled as heuristic and are not presented as legal conclusions (constitution 2.2.0). | PASS |
| IV. Verifiable Pipeline Stages | Stages `extract → split → meta → index → check → retrieve → review → report → render` are separate modules with a CLI check; the `needs_ocr` flag is never silently turned into "full text". | PASS |
| V. Confidential Client Data | The LLM provider is named in the constitution (2.1.0) and in the plan: Anthropic (R3). Report storage for 30 days and the authentication requirement before external access come from constitution 2.2.0 (R14). Sending: one clause + norms; translation: only `explanation_es` and article IDs (not the contract text). The gap check (R10) sends nothing to an external service. Logs contain no contract text. The contract is deleted right after the report. Embeddings are local. The report is stored locally for 30 days without contract text (R14). | PASS (amendments 2.1.0 and 2.2.0 applied; provider terms check is required before the first real contract) |
| V. External quality services (Codecov, Code Climate) | They receive source code and the coverage report, but not client contracts (fixtures are synthetic). The `data/`, `.env`, `.venv/` exclusions are set in the configs and checked in CI. The constitution forbids other external services from receiving client data without separate approval — no such data is sent here. | PASS, provided the exclusions are in the configs |
| Technical: Chroma `ar_law`, cosine; record IDs `{regime}-{article}` | Met. The ID scheme for CABA records is `{regime}-{article}`, where regime is the CABA regime name (see data-model). | PASS |
| Technical: Python 3.11, pinned dependencies | The plan requires `requirements.txt` with pinned versions as a feature-readiness criterion. | PASS (done in tasks) |
| Workflow: changes in `src/kb/`, `src/ingest/` need a verification step | Covered in quickstart and in the T-ingest tasks. | PASS |

**Discrepancies to resolve before implementation**:
1. The description says `src/ingest/`, `src/kb/`, `src/retrieval/` are already implemented, but **they are not in the working tree**
   (`src/` was missing; `data/chroma` was absent). The plan relies on the described interfaces; before the tasks, either confirm
   that the code lives in another branch/repository, or treat these modules as "to be implemented".
2. Existing JSON records use `valid_to: null` and ISO dates, not `99991231` / `YYYYMMDD`. This must be
   fixed in the `index` stage (normalize at indexing time, not by editing the source JSON — the constitution requires
   keeping `source_url` and dates from the source).

**Constitution amendment 2.1.0 (applied 2026-10-13)**: Principle V now names the provider "Anthropic, model set in
configuration" and requires that data-retention and training terms be verified and recorded before the first real
client contract. The Sync Impact Report and migration note are updated in `.specify/memory/constitution.md`. The
verification condition stays open until the first real contract (see research.md R3, item 2).

**Constitution amendment 2.2.0 (applied 2026-10-13)**: Principle III — heuristic findings are labeled as heuristic;
Principle V — reports are stored locally for 30 days without contract text, by `report_id`, with authentication before
external access; Technical Constraints and Development Workflow — stores, quality tools, CI on GitHub Actions,
testing of `required_element` patterns, and an extended list of artifacts not to commit.

**Complexity Tracking**: no constitution violations. Report storage (30 days, SQLite) is allowed by the owner and
recorded in spec §4 and AC15–AC16. The only new persistent entity is the report without contract text (R14).
The gap heuristic (R10) is a deliberate simplification: it documents its failure modes in code (principle IV).

## Code quality and coverage (CI)

| Tool | What it does in the project | Input | Config in the repository |
|------|-----------------------------|-------|--------------------------|
| `pytest-cov` (library, dev dependency) | measures coverage for `pytest tests/unit tests/contract` (integration only locally) | — | `pyproject.toml` (`[tool.coverage.*]`, sources `src/`) |
| Codecov | uploads `coverage.xml`, shows uncovered lines and where to improve tests; the coverage threshold for new lines is enforced in PR checks | `coverage.xml` | `codecov.yml` |
| Code Climate | analyzes sources (complexity, duplication, style) and lists improvements; Python engines are enabled via `.codeclimate.yml` | `src/` and `tests/` sources | `.codeclimate.yml` |

Rules that apply to both services:
- Only the `src/` and `tests/` source code and the coverage report are sent. The paths `data/`, `.env`, `.venv/`, `data/reports.db`
  are excluded in `codecov.yml` (`ignore`) and `.codeclimate.yml` (`exclude_paths`). A CI task checks this.
- Test fixtures are synthetic only (constitution V); the services never receive client contracts.
- The tokens `CODECOV_TOKEN` and `CC_TEST_REPORTER_ID` are stored in CI secrets; their values are not written to the spec, plan,
  logs, or fixtures (constitution V).
- A failed upload to a service does not block the build if the tests pass; the coverage threshold is checked locally with
  `pytest --cov --cov-fail-under=<threshold>` (the threshold is set in the tasks).
- CI — GitHub Actions (`.github/workflows/ci.yml`): Python 3.11, `pytest tests/unit tests/contract --cov`, upload to
  Codecov and Code Climate. Uploads do not block the build (`continue-on-error`). Integration tests do not run in CI.
- Code Climate analysis runs on the platform after the repository is connected; CI handles only the coverage report.
- Repository: `git init`, main branch `001-contract-review-mvp`; `.gitignore` excludes `.env`, `.venv/`,
  `data/chroma/`, `data/reports.db`, `coverage.xml`, `__pycache__/`. `.env.example` is a template without values.

A test set counts as "covered" when Codecov shows no uncovered branches in `src/review/`, `src/report/`
and `src/api/` (the modules critical under the constitution: norm-reference validation, regime selection, error handling).

## Project Structure

### Documentation (this feature)

```text
specs/001-contract-review-mvp/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0: decisions R1–R14
├── data-model.md        # Phase 1: clause, review, report, norms, config
├── quickstart.md        # Phase 1: end-to-end validation scenario
├── contracts/
│   └── api.md           # Phase 1: FastAPI HTTP contracts
└── tasks.md             # Phase 2 — created by /speckit-tasks, not here
```

### Source Code (repository root)

```text
src/
├── ingest/                    # already implemented (per the description) — reused
│   ├── extract.py             # PyMuPDF / python-docx, needs_ocr flag
│   ├── split.py               # split by CLÁUSULA / ARTÍCULO / numbering + preamble
│   └── meta.py                # contract type, signing date
├── kb/                        # already implemented (per the description) — reused
│   ├── embedder.py            # multilingual-e5-large, query:/passage: prefixes
│   ├── dates.py               # dates → int YYYYMMDD, open-ended → 99991231 (normalization)
│   └── index.py               # Chroma PersistentClient, collection ar_law, cosine
├── retrieval/
│   └── retrieve.py            # Retriever: filters on jurisdiction, contract_type, regime, dates
├── review/                    # NEW (T5)
│   ├── regime.py              # regime selection by signing date (one per contract)
│   ├── clause_review.py       # one clause → LLM request → ClauseReview (reference validation)
│   ├── stamp_tax.py           # CABA stamp tax: vivienda única, payer, rate status
│   ├── gaps.py                # deterministic check of mandatory elements (R10)
│   ├── llm/
│   │   ├── base.py            # LLMClient interface (Protocol)
│   │   └── anthropic_client.py  # implementation + retries (R5)
│   └── orchestrator.py        # pipeline: clauses in parallel, Report assembly
├── report/                    # NEW (T6–T7)
│   ├── model.py               # Report, ClauseReview, Finding (pydantic)
│   ├── render.py              # translation to EN/RU over the language-neutral Report (T7)
│   ├── i18n/                  # fixed disclaimer and label texts; Spanish glossary
│   └── disclaimer.py
├── store/                     # NEW (R14)
│   └── reports.py             # SQLite: save/get/purge_expired, 30-day TTL
├── api/                       # NEW (API)
│   ├── app.py                 # FastAPI app factory, error handlers, lifespan (purge)
│   ├── routes_reviews.py      # POST /v1/reviews
│   ├── routes_reports.py      # GET /v1/reports/{report_id}?lang=
│   ├── errors.py              # error codes → HTTP
│   └── deps.py                # Settings, Retriever, LLMClient, ReportStore (DI)
└── config.py                  # pydantic-settings: thresholds, k, LLM model, limits

data/
├── laws/nacional/             # CCyC locación / compraventa + DNU 70/2023 + Ley 27.551 (present)
├── laws/caba/                 # sellos / Ley Tarifaria (empty — fill before T5)
├── reference/                 # reference contracts (out of MVP)
├── reports.db                 # SQLite reports, 30-day retention (in .gitignore)

# Quality configs (repository root)
pyproject.toml                 # pytest, pytest-cov (sources src/, branch coverage)
codecov.yml                    # Codecov: ignore data/, .env, .venv/; coverage targets
.codeclimate.yml               # Code Climate: radon/bandit/duplication engines, exclude_paths
.github/workflows/ci.yml       # GitHub Actions: tests → Codecov and Code Climate
.gitignore                     # secrets, .venv, data, reports, coverage
.env.example                   # variable template without values
└── glossary/es_terms.json     # ES term → EN/RU, for brackets in the translation (T7)

tests/
├── unit/                      # split, meta, regime, clause_review (with fake LLM), stamp_tax, render
├── integration/               # retrieval on the real index (check queries)
└── contract/                  # HTTP contracts via httpx, synthetic contract fixtures
```

**Structure Decision**: one Python package `src/` with module boundaries per pipeline stage (ingest → kb →
retrieval → review → report → api). The `ingest/kb/retrieval` modules keep their interfaces, except date
normalization in `kb/dates.py`. A separate backend/frontend layout was not chosen: the MVP has no frontend.

## Phase 0 / Phase 1 outputs

- [research.md](./research.md) — all NEEDS CLARIFICATION items resolved (R1–R14).
- [data-model.md](./data-model.md) — entities, fields, validation, run state transitions.
- [contracts/api.md](./contracts/api.md) — endpoints, schemas, error codes.
- [quickstart.md](./quickstart.md) — validation scenario.

Extension hooks: `.specify/extensions.yml` is absent — no hooks were run.
