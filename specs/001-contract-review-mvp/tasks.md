# Tasks: Contract Review MVP (CABA, Phase 0)

**Input**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Constitution**: 2.2.0 (`.specify/memory/constitution.md`)

**Tests**: included. For each new module the test is written before the code: unit — with fake LLM and embedder; integration — retrieval on the real index; contract — HTTP via httpx.

## Repository state at generation time

| Module | State | How it is marked in the tasks |
|--------|-------|-------------------------------|
| `src/ingest/` (extract, split, meta) | **not found** in the tree | implement (T1) |
| `src/kb/` (embedder, dates, index) | **not found** | implement (T2) |
| `src/retrieval/retrieve.py` | **not found** | implement (T3) |
| `data/laws/caba/codigo_fiscal_sellos.json` | present (3 records) | verify and extend (T4) |
| `data/laws/nacional/*.json` | present (locación, compraventa) | verify (T4) |
| `data/chroma/` | absent | created by re-indexing (T4) |
| `tests/`, `requirements.txt` | absent | created in Setup |
| `.venv`: chromadb 1.5.9, pymupdf 1.28.2, python-docx, sentence-transformers, httpx | installed | pin the versions |
| `.venv`: fastapi, uvicorn, anthropic, pytest, pydantic-settings | not found | install (T001–T002) |

If `ingest/kb/retrieval` exist somewhere else (another branch or repository), the path must be given before T1–T3:
the tasks become "verify + move" instead of "implement".

## Decisions made during generation (deviations from the request)

1. **`REPORT_RETENTION_DAYS = 30`, not 7.** The owner approved 30 days (spec §4, AC15, R14, data-model §8, constitution 2.2.0).
   The value 7 from the request was not applied. Changing the period is a separate owner decision, after which the spec and the constitution change.
2. **`LLM_MODEL = claude-sonnet-5-5`.** The identifier `claude-sonnet-5` in the request does not match the model ID; `claude-sonnet-5-5` is used (as in plan.md R3 and data-model §8).
3. **Principle V is closed in constitution 2.2.0, but the provider condition is still open.** The data-retention and training terms at Anthropic must be recorded in plan.md (R3, item 2) before the first real contract. Task T069 blocks real use, not development on synthetic data.

## Format: `- [ ] [TaskID] [P?] [Story?] Description with file path`

- **[P]** — can run in parallel (different files, no dependency on unfinished tasks)
- **[US1]/[US2]** — only in user-story phases
- The blocks T1–T4 and T5 from the request correspond to phases 2 and 3 below.

---

## Phase 1: Setup (shared infrastructure)

**Purpose**: dependencies, package structure, configuration.

- [X] T001 Create `requirements.txt` with pinned versions: `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `chromadb==1.5.9`, `sentence-transformers` (version from `.venv`), `pymupdf==1.28.2`, `python-docx`, `anthropic`, `httpx`. Take the versions from `.venv` (`pip freeze`), not from the internet
- [X] T002 Create `requirements-dev.txt`: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`; install `pip install -r requirements.txt -r requirements-dev.txt` into `.venv`
- [X] T003 [P] Create the packages: `src/__init__.py`, `src/ingest/__init__.py`, `src/kb/__init__.py`, `src/retrieval/__init__.py`, `src/review/__init__.py`, `src/review/llm/__init__.py`, `src/report/__init__.py`, `src/store/__init__.py`, `src/api/__init__.py`, `tests/__init__.py`, `tests/unit/__init__.py`, `tests/contract/__init__.py`, `tests/integration/__init__.py`
- [X] T004 [P] Create `src/config.py` (pydantic-settings) with the keys from data-model §8: `RETRIEVAL_K=5`, `CONFIDENCE_THRESHOLD=0.3`, `EMBED_MODEL=intfloat/multilingual-e5-large`, `CHROMA_PATH=data/chroma`, `CHROMA_COLLECTION=ar_law`, `LLM_PROVIDER=anthropic`, `LLM_MODEL=claude-sonnet-5-5`, `LLM_MAX_ATTEMPTS=3`, `LLM_TIMEOUT_S=30`, `LLM_CONCURRENCY=5`, `ANTHROPIC_API_KEY` (secret, `SecretStr`, never logged), `OCR_ENABLED=false`, `OCR_LANG=spa`, `MAX_UPLOAD_MB=10`, `REPORTS_DB_PATH=data/reports.db`, `REPORT_RETENTION_DAYS=30`
- [X] T005 [P] Create `tests/conftest.py` with fixtures: `fake_llm` (returns a given `ClauseReviewOutput`), `fake_embedder` (deterministic vectors), `tmp_chroma` (`chromadb.EphemeralClient`), `settings_override`
- [X] T006 [P] Create `tests/fixtures/make_fixtures.py`: generates synthetic contracts (python-docx, PyMuPDF) into `tests/fixtures/`: `locacion_2026_synthetic.docx` (date "a los 15 días del mes de marzo de 2026", 10 clauses), `locacion_2022_synthetic.docx` (date in 2022), `compraventa_2025_synthetic.docx`, `no_date_synthetic.docx`, `locacion_no_price_synthetic.docx` (no price and no term), `scan_no_text_synthetic.pdf` (image-only page with no text), `unreadable_synthetic.pdf` (broken file). No personal data (constitution V)

---

## Phase 2: Foundational — blocks T1–T4 (block all stories)

**Purpose**: ingest, kb, retrieval and the norm index. Per the request, phase 3 (T5) starts only after these blocks pass the check.

**⚠️ CRITICAL**: do not start phase 3 without a green gate T026.

### T1. Ingest (implement — not found in the tree)

**Tests before code.**

- [X] T007 [P] Extraction test in `tests/unit/test_extract.py`: PDF with a text layer → `needs_ocr=False`; scan without text → `needs_ocr=True`; DOCX → text; broken file → `DocumentUnreadable` exception. Detect the file type by signature (`%PDF`, `PK\x03\x04`), not by extension
- [X] T008 Implement `src/ingest/extract.py`: function `extract(data: bytes) -> ContractDocument` (data-model §1). PDF — `fitz.open(stream=data, filetype="pdf")`; DOCX — `python-docx` from `io.BytesIO`. Do not write the file to disk. A comment at the top of the file lists the failure modes (principle IV): a page counts as "without a text layer" if its text is empty after `strip()`
- [X] T009 [P] Splitting test in `tests/unit/test_split.py`: markers `CLÁUSULA PRIMERA`, `ARTÍCULO 3`, `3.`; preamble is a separate block; `clause_id` = `c-01`, `c-02`…; an empty clause is dropped and recorded in `warnings`; no markers → `NoClausesDetected`. Do not trim the clause text of its marker
- [X] T010 Implement `src/ingest/split.py`: `split(text_es: str) -> tuple[Preamble, list[Clause]]` per data-model §2. Document the failure modes in the docstring (principle IV)
- [X] T011 [P] Metadata test in `tests/unit/test_meta.py`: contract type (`compraventa`/`locacion`) from the text; date "a los 15 días del mes de marzo de 2026" → `2026-03-15`; ambiguous or missing date → `None`; a date from the request takes priority, the conflict is recorded in `warnings`
- [X] T012 Implement `src/ingest/meta.py`: `detect_meta(text_es, user_signing_date=None) -> ContractMeta`. Find the type and the date with regexes; document the failure modes (principle IV)

### T2. KB: dates, embedder, index (implement — not found in the tree)

- [X] T013 [P] Date test in `tests/unit/test_dates.py`: ISO `2023-12-29` → `20231229`; `valid_to: null` → `99991231`; `""` → error (`DateParseError`); invalid date → error. Constitution II: an empty string is not allowed as a placeholder
- [X] T014 Implement `src/kb/dates.py`: `to_yyyymmdd(value: str | None, open_end: bool) -> int`
- [X] T015 [P] Embedder test in `tests/unit/test_embedder.py` (without loading the model): documents are encoded with the prefix `passage: `, queries with `query: `; mixing prefixes is not allowed (checked at the class API level)
- [X] T016 Implement `src/kb/embedder.py`: class `E5Embedder` with methods `embed_passages(texts)` and `embed_query(text)`; the model `intfloat/multilingual-e5-large` is loaded lazily; `HF_HUB_OFFLINE` is respected
- [X] T017 [P] Index test in `tests/unit/test_index.py` on `tmp_chroma` with `fake_embedder`: the collection `ar_law` is created with `metadata={"hnsw:space": "cosine"}`; ID = `{regime}-{article}`; `valid_from_i`/`valid_to_i` are `int`; a record with an unparseable date → indexing refused; the `kind` field defaults to `"norm"`
- [X] T018 Implement `src/kb/index.py`: CLI `python -m src.kb.index build --laws data/laws` (recursive, including `data/laws/caba/`) and `python -m src.kb.index check` (queries from quickstart §1). Dates normalized via `dates.py`; `valid_to: null` → `99991231`

### T3. Retrieval (implement — not found in the tree)

- [X] T019 [P] Retrieval test in `tests/unit/test_retrieve_filters.py` (no index): the built `where` contains `jurisdiction $in [nacional, CABA]`, `regime`, `valid_from_i $lte D`, `valid_to_i $gte D`; score = `1 − distance`
- [X] T020 Test on the real index in `tests/integration/test_retrieve.py` (marker `integration`): the query "plazo mínimo locación" with D=20231229 → only `Ley 27.551-1198`; with D=20231230 → only `DNU 70/2023-1198`; a CABA-related query (sellos) returns records with `jurisdiction=CABA`; no other provinces (AC5)
- [X] T021 Implement `src/retrieval/retrieve.py`: `Retriever.search(RetrievalQuery) -> list[RetrievedNorm]`; Chroma specifics only here (R2)

### T4. KB content and re-indexing (verify and extend)

- [ ] T022 Verify `data/laws/nacional/ccyc_compraventa.json`: it contains records for both regimes (`Ley 27.551` and `DNU 70/2023`) with `valid_from`/`valid_to`, `source_url`, and `verbatim` for each record. If they are missing, record it in the task notes and do not proceed until fixed
- [X] T023 Extend `data/laws/caba/codigo_fiscal_sellos.json`: add `"kind": "tax"` to all three records; add a structured `params` block with the numbers from the text (today they are only in the `text` string): for `sellos-compraventa-vivienda-unica` — `threshold_ars: 226100000`, `rate_excess: 0.035`, `split: {buyer: 0.5, seller: 0.5}`, `base: "max(price, valuacion_fiscal)"`; for `sellos-compraventa-no-vivienda-unica` — `rate: 0.027`. Keep `sellos-locacion` with `params: null` and a `note` "PENDIENTE". Constitution I: legal numbers are not hard-coded in code; they come from the KB
- [X] T024 [P] KB schema test in `tests/unit/test_kb_schema.py`: each record has `source_url`, `regime`, `article`, `valid_from`, `kind`; `required_element` records have `element`, `patterns` (non-empty list of regexes that compile), `level`; records with `verbatim: false` and a `note` carry a marker that they need checking against the source
- [X] T025 Re-indexing: `rm -rf data/chroma && python -m src.kb.index build --laws data/laws && python -m src.kb.index check`. `data/chroma/` is generated and listed in `.gitignore`; before deleting, check that the folder exists (it did not exist at the time). Record the result (record count, distribution by `jurisdiction` and `regime`) in the "Notes" block at the bottom of this file
- [ ] T026 **GATE T1–T4**: `pytest tests/unit/test_extract.py tests/unit/test_split.py tests/unit/test_meta.py tests/unit/test_dates.py tests/unit/test_embedder.py tests/unit/test_index.py tests/unit/test_retrieve_filters.py tests/unit/test_kb_schema.py tests/integration/test_retrieve.py -m "" -q` — all green. Start phase 3 only after this

**Checkpoint**: ingest, kb and retrieval pass the check; the index is built with cosine and YYYYMMDD.

---

## Phase 3: User Story 1 — Contract review and report in Spanish (Priority: P1) 🎯 MVP

**Story goal**: contract upload → type and date → regime by signing date → per-clause analysis via the LLM → gaps and CABA stamp tax → report (AC1–AC4, AC6, AC7, AC10, AC12–AC14, AC17; UC1–UC5).

**Independent test**: `POST /v1/reviews` on `locacion_2026_synthetic.docx` (with a fake LLM) returns a `report` with `regime = "DNU 70/2023"`, clauses whose `article_refs` ⊆ the norms found, `contract_gaps` with heuristic entries, and `stamp_tax` with `rate_status = "pending"`.

**Block T5 (from the request)**: `regime.py`, `clause_review.py` (LLM), `stamp_tax.py`, `gaps.py`, `orchestrator.py`. Tests before code.

### Tests for US1 (write first, make sure they fail)

- [X] T027 [P] [US1] Regime test in `tests/unit/test_regime.py`: D=20260315 → `DNU 70/2023`; D=20221015 → `Ley 27.551`; D=20231229 → `Ley 27.551`; D=20231230 → `DNU 70/2023`; `contract_type=locacion` and `compraventa` both select the regime by date (spec §3); D not set → `SigningDateRequired`; one regime for the whole contract (a single `regime` field)
- [X] T028 [P] [US1] Report model test in `tests/unit/test_report_model.py`: `Finding.article_refs ⊆ retrieved_ids` (otherwise `LLM_INVALID_OUTPUT`); `no_norm_found=True` ⇔ `article_refs=[]`; `type in {risk, mismatch, gap}` requires `article_refs` or `no_norm_found`; `source="heuristic"` only with `type="gap"`, exactly one `article_refs` of kind `required_element`, `needs_manual_review=True`, non-empty `searched_patterns`; `StampTaxResult` for `locacion`: `amount_ars is None` and `rate_status == "pending"`
- [X] T029 [P] [US1] Clause analysis test in `tests/unit/test_clause_review.py` with `fake_llm`: a valid response → `ClauseReview`; `best_score < 0.3` → `needs_manual_review=True`; no norms → `best_score=None`, `needs_manual_review=True`, `no_norm_found=True`; an invalid model response three times → `LLMInvalidOutput`; provider failure three times → `LLMUnavailable`; the LLM request contains only the clause text and the norms found (not the whole contract)
- [X] T030 [P] [US1] Stamp tax test in `tests/unit/test_stamp_tax.py`: compraventa vivienda única ≤ 226 100 000 → `exemption=True`, `amount=0`; above the threshold → 3.5 % on the excess only, split 50/50; compraventa not vivienda única → 2.7 %; base = `max(price, valuacion_fiscal)`; no `valuacion_fiscal` in the text → no amount, warning in `warnings`; locación → `amount_ars=None`, `rate_status="pending"`, payer stated
- [X] T031 [P] [US1] Gap test in `tests/unit/test_gaps.py`: an element found by at least one pattern anywhere in the text (including the preamble) → no gap; not found → `Finding(type="gap", source="heuristic", needs_manual_review=True, searched_patterns=[...])`; patterns ignore case and diacritics; no external calls (the client mock fails if called)
- [X] T032 [P] [US1] Orchestrator test in `tests/unit/test_orchestrator.py` with fakes: clauses run in parallel with the `LLM_CONCURRENCY` semaphore; a failure in any clause fails the whole run with an exception and no `Report`; text buffers are cleared in `finally` (checked through a fake `ContractDocument` with a flag)
- [X] T033 [P] [US1] Error contract test in `tests/contract/test_reviews_errors.py` (httpx `ASGITransport`): 415 `UNSUPPORTED_FORMAT` for `README.md`; 413 `FILE_TOO_LARGE`; 422 `DOCUMENT_UNREADABLE` for `unreadable_synthetic.pdf`; 422 `OCR_UNAVAILABLE` for `scan_no_text_synthetic.pdf` with `OCR_ENABLED=false`; 422 `NO_CLAUSES_DETECTED`; 422 `SIGNING_DATE_REQUIRED` for `no_date_synthetic.docx`; 422 `LANG_UNSUPPORTED` for `lang=fr`; the error body follows contracts/api.md §4

### Implementation for US1

- [X] T034 [US1] Implement `src/report/model.py` (pydantic v2) per data-model §2–§6: `Clause`, `Preamble`, `ContractMeta`, `RetrievedNorm`, `Finding` with the validators from T028, `ClauseReview`, `StampTaxResult`, `Report` (without `report_id` and `expires_at` — added in US2). The `Finding` validator follows data-model §4 word for word
- [X] T035 [US1] Implement `src/review/regime.py`: `select_regime(D: int, contract_type) -> RegimeChoice` over KB records with `jurisdiction=nacional`, the contract's `contract_type`, and `valid_from_i ≤ D ≤ valid_to_i`. Regimes are not hard-coded (R5)
- [X] T036 [US1] Implement `src/review/llm/base.py` (Protocol `LLMClient.review_clause(...)`) and `src/review/llm/anthropic_client.py`: tool use with the JSON schema `ClauseReviewOutput`, `temperature=0`, `model=settings.LLM_MODEL`, timeout `LLM_TIMEOUT_S`, up to `LLM_MAX_ATTEMPTS` attempts with pauses of 1 s and 3 s (R8). Do not write the contract text to the logs
- [X] T037 [US1] Create the prompt `src/review/prompts/clause_review_es.md`: analysis strictly in Spanish; no references outside the norms provided; paraphrase rather than quote more than 80 characters; output only JSON per the schema
- [X] T038 [US1] Implement `src/review/clause_review.py`: `review_clause(clause, retrieved, llm) -> ClauseReview`; reference validation via the model from T034; `needs_manual_review` by `CONFIDENCE_THRESHOLD` (T029)
- [X] T039 [US1] Implement `src/review/stamp_tax.py` per the T030 test: parameters only from the `params` of KB records (T023), no numbers in code; locación → `pending`
- [X] T040 [US1] Create `data/laws/nacional/required_elements.json`: records with `kind="required_element"` for locación and compraventa (`element`, `patterns`, `level`, `source_url`, `article`, `regime`, dates). **Attention**: the content must be checked against the source by the owner or a lawyer before indexing (constitution, Development Workflow). The patterns are checked by a test on synthetic contracts (`locacion_2026_synthetic.docx` with a price, `locacion_no_price_synthetic.docx` without one)
- [X] T041 [US1] Implement `src/review/gaps.py` per the T031 test: a docstring with the failure modes (false negatives, false positives, elements in annexes); no external calls
- [X] T042 [US1] Re-index after T040: `python -m src.kb.index build --laws data/laws` (no `rm -rf` if the index already exists — a full rebuild with `rm -rf data/chroma` only if the schema changes) and `check`
- [X] T043 [US1] Implement `src/review/orchestrator.py`: `run_review(document, meta, retriever, llm, settings) -> Report`; clauses in parallel, `LLM_CONCURRENCY` semaphore; assembles `contract_gaps`, `stamp_tax`, `summary`; `finally` clears the buffers
- [X] T044 [US1] Implement `src/api/errors.py`: exceptions → codes from contracts/api.md §1 and HTTP statuses; the error body per §4 with `message` (ES) and `message_en`; no contract text
- [X] T045 [US1] Implement `src/api/deps.py` and `src/api/app.py`: `Settings`, `Retriever`, `LLMClient`, `E5Embedder` as dependencies; the embedder and Chroma are created once in `lifespan` (R9); dependencies can be replaced for tests
- [X] T046 [US1] Implement `src/api/routes_reviews.py`: `POST /v1/reviews` (multipart `file`, `signing_date`, `lang`) → `Report` (without `report_id`/`rendered` — added in US2); `signing_date` takes priority over the date in the text (data-model §2)
- [X] T047 [US1] Run T033 and add missing checks until green
- [X] T048 [US1] End-to-end test `tests/contract/test_reviews_e2e.py` (fake LLM): `locacion_2026` → `DNU 70/2023`; `locacion_2022` → `Ley 27.551`; `no_date` → 422, then with `signing_date=2025-06-01` → 200; the LLM fails on all attempts → 503 `LLM_UNAVAILABLE`, no `report` in the body (AC14)
- [X] T049 [US1] UC4/AC10 test: a synthetic clause with no norm matches → `needs_manual_review=True` in the report and in `summary.manual_review` (test in `tests/contract/test_reviews_e2e.py`)
- [X] T050 [US1] Logging in `src/api/logging.py`: `request_id`, stage, duration, error code, `clause_id`, model, token count; test `tests/unit/test_logging.py` via `caplog`: no line from the synthetic contract text appears in the logs (constitution V)

**Checkpoint**: US1 works independently: POST /v1/reviews returns a Spanish report, errors come without partial reports, gap heuristics are flagged.

---

## Phase 4: User Story 2 — Report storage and language (Priority: P2)

**Story goal**: the report is stored for 30 days by `report_id`, served in `es|en|ru` through GET, with the disclaimer in every render (AC8, AC11, AC15, AC16; spec §4; R6, R14; T6–T7 from the plan).

**Independent test**: after `POST /v1/reviews`, GET `/v1/reports/{report_id}?lang=ru` returns a render with the disclaimer in Russian; after the retention period — 404; `lang=es` does not call the LLM.

### Tests for US2 (first)

- [X] T051 [P] [US2] Storage test in `tests/unit/test_report_store.py`: save → get; `expires_at = created_at + 30 days` (`REPORT_RETENTION_DAYS`); an expired record → `None`; purge removes expired records; `schema_version` mismatch → `None`; the file is created with mode `0600`; `report_json` has no `text_es` field (checked against the schema)
- [X] T052 [P] [US2] Render test in `tests/unit/test_render.py` with a fake LLM: the disclaimer is present for every `lang`; for `lang=es` the LLM is not called; for `en`/`ru` only `explanation_es` and article IDs go to the LLM (checked on the fake's arguments); a legal term in the translation appears in brackets with the Spanish original (`locación (аренда)`); an LLM response with a long quote (more than 80 consecutive characters from `explanation_es`) is rejected; on LLM failure → `LLMUnavailable`, no partial translation
- [X] T053 [P] [US2] Contract test in `tests/contract/test_reports_api.py`: `POST /v1/reviews` returns `report_id` (UUID4) and `expires_at`, `rendered` is present; `GET /v1/reports/{id}?lang=en` → 200 and `Cache-Control: no-store`; unknown id → 404 `REPORT_NOT_FOUND`; expired id → 404 with the same body (AC15); `lang=fr` → 422 `LANG_UNSUPPORTED`; a storage write failure → 500 `REPORT_STORE_FAILED`, with no report in the response

### Implementation for US2

- [X] T054 [US2] Implement `src/store/reports.py`: SQLite at `REPORTS_DB_PATH`, table `reports(report_id TEXT PK, created_at TEXT, expires_at TEXT, report_json TEXT)` (data-model §10); `save`, `get`, `purge_expired`; purge at startup and before every read and write
- [X] T055 [US2] Create `src/report/i18n/disclaimer.py` and `src/report/i18n/labels.py`: disclaimer texts in `es`, `en`, `ru`, each containing the three AC11 statements: (a) only the Spanish original is legally binding, (b) the report is informational, (c) the final decision is made by a qualified lawyer. The text is fixed and is not translated by the model (R12)
- [X] T056 [P] [US2] Create `data/glossary/es_terms.json`: a starter glossary — `compraventa`, `locación`, `locador`, `locatario`, `vendedor`, `comprador`, `impuesto de sellos`, `vivienda única`, `cláusula`, `valuación fiscal` with `en` and `ru` translations
- [X] T057 [US2] Implement `src/report/render.py`: `render_report(report, lang, llm, glossary) -> RenderedReport`; for `es` without the LLM; for `en`/`ru` — one LLM call per clause with `explanation_es` and article IDs; glossary terms in brackets; a check for long quotes (T052)
- [X] T058 [US2] Implement `src/api/routes_reports.py`: `GET /v1/reports/{report_id}?lang=es|en|ru` (contracts/api.md §2), header `Cache-Control: no-store`, only the hash prefix of `report_id` in the logs (R14)
- [X] T059 [US2] Extend `src/api/routes_reviews.py`: after `run_review` — `save` to the store (failure → 500 `REPORT_STORE_FAILED`); the response contains `report_id`, `expires_at`, `report`, `rendered`, `lang`
- [X] T060 [US2] Hook purge into `lifespan` (`src/api/app.py`) and a startup test: expired records are removed at startup
- [X] T061 [US2] Run T051–T053 until green; check `pytest tests/contract/test_reports_api.py -q`

**Checkpoint**: US2 works independently: the report is stored, served in three languages, and deleted after 30 days.

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: quality, CI, acceptance, production blockers.

- [X] T062 [P] Check `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`): once `src/` and `tests/` exist, `pytest --cov` produces `coverage.xml`
- [X] T063 [P] Check `.github/workflows/ci.yml`: the run of `pytest tests/unit tests/contract --cov` passes locally with the same commands; use `pytest` without the integration exclusion if needed. The model cache and the removal of `HF_HUB_OFFLINE=1` were applied (see Notes)
- [X] T064 [P] Check `codecov.yml` and `.codeclimate.yml`: exclusions match `.gitignore` (`data/`, `.env`, `.venv/`)
- [ ] T065 Run `specs/001-contract-review-mvp/quickstart.md` steps 1–8 on the synthetic fixtures; record the results in the notes
- [ ] T066 Performance measurement: a 10-clause synthetic contract with the real LLM and the real index; 95% of runs < 60 s (spec §4). Measure over 20 runs; record the result in the notes. Blocks acceptance, not CI
- [ ] T067 Decision on AC9 (progress indicator): the API contract has no status endpoint and there is no frontend. Choose: (a) `GET /v1/reviews/{id}/status`, which requires storing run state — conflicts with spec §4; (b) progress streaming via SSE from `POST /v1/reviews`; (c) defer to the UI phase. Owner's decision; record it in spec §6 (AC9) and in the plan
- [X] T068 Ruff: `ruff check src tests` and `ruff format --check src tests` pass without errors; settings in `pyproject.toml`
- [ ] T069 **Blocker for the first real contract**: record in `plan.md` (R3, item 2) the data-retention and training terms at Anthropic for the project's API account. Do not process real contracts before this (constitution 2.2.0, principle V)
- [ ] T070 **Production blocker**: replace the `verbatim: false` texts with literal texts from the sources (`ccyc_*.json`, `codigo_fiscal_sellos.json`, DNU 70/2023, Ley 27.551, Ley Tarifaria 2026); fill `sellos-locacion` (currently `[COMPLETAR CON TEXTO OFICIAL]`); re-index and run `check`. Constitution: each record is checked against its source before indexing
- [ ] T071 Update `specs/001-contract-review-mvp/plan.md` and `tasks.md` (notes): final test counts, results of T025, T065, T066

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T001 → T002; T003–T006 in parallel after T001
- **Foundational (Phase 2, T1–T4)**: after Setup. Inside: T1 and T2 are independent (different files) — in parallel; T3 after T2 (needs `embedder` and `index`); T4 after T1–T3; T026 is the gate
- **US1 (Phase 3, block T5)**: after T026. Inside: tests T027–T033 in parallel; `model.py` (T034) before the other modules; `regime` (T035) and `stamp_tax`/`gaps` (T039, T041) depend on KB records T023 and T040; `orchestrator` (T043) after all review modules; API (T044–T046) after the orchestrator
- **US2 (Phase 4)**: after US1 (needs `Report` and `POST /v1/reviews`). Tests T051–T053 in parallel; `store` (T054) and `render` (T057) are independent of each other; `routes_reviews` (T059) after the store
- **Polish (Phase N)**: after US1 and US2

### User Story Dependencies

- **US1**: depends on Foundational
- **US2**: depends on US1 (report model and endpoint); can start with the tests and the store (T051, T054) in parallel with the end of US1

### Parallel Opportunities

- Setup: T003, T004, T005, T006 in parallel
- Foundational: tests T007, T009, T011, T013, T015, T017, T019 in parallel with each other
- US1 tests: T027–T033 in parallel
- US2: T051–T053 in parallel; T056 in parallel with T054

### Parallel Example: US1 tests

```bash
pytest tests/unit/test_regime.py          # T027
pytest tests/unit/test_report_model.py    # T028
pytest tests/unit/test_clause_review.py   # T029
pytest tests/unit/test_stamp_tax.py       # T030
pytest tests/unit/test_gaps.py            # T031
```

---

## Implementation Strategy

### MVP First (US1)

1. Phase 1: Setup
2. Phase 2: T1–T4 and gate T026
3. Phase 3: US1 (block T5)
4. **Stop and check**: `pytest tests/contract/test_reviews_e2e.py` and a manual run on `locacion_2026_synthetic.docx` with the real LLM (synthetic only)
5. Do not move to real contracts before T069

### Incremental Delivery

1. Setup + Foundational → index with cosine and YYYYMMDD, retrieval verified
2. US1 → Spanish report (MVP)
3. US2 → 30-day storage, EN/RU translations
4. Polish → CI, performance, blockers T069–T070

---

## Notes

### Execution results (`/speckit-implement`)

- **Tests**: `pytest tests -m ""` → 141 passed, 1 xfailed (`test_sale_and_lease_both_have_national_regimes`). Coverage of `src/` (unit + contract, without integration) — 88 %; `ruff check` and `ruff format --check` are clean.
- **Index**: `data/chroma` built with `python -m src.kb.index build --laws data/laws` (7 records, cosine). `check` for "plazo mínimo locación": Ley 27.551 art.1198 = 0.910, DNU 70/2023 art.1198 = 0.910, Ley 27.551 art.1221 = 0.855, DNU 70/2023 art.1221 = 0.835, CABA sellos-locacion = 0.812. All scores are above the 0.3 threshold — the threshold is provisional (AC10).
- **T022 — blocker (data)**: `data/laws/nacional/ccyc_compraventa.json` contained three copies of CABA records (identical to `caba/codigo_fiscal_sellos.json`) and no sale norms. The copies were removed (the file is now `[]`). The CCyC compraventa norms (arts. 1123–1171) and the DNU 70/2023 / Ley 27.551 regimes for sales were **not added**: they cannot be written from memory (constitution I) and need a primary source. As a result, `regime = null` for sales, and the report says so (test `test_sale_without_national_norms_reports_no_regime`).
- **T040 — blocker (data)**: `data/laws/nacional/required_elements.json` was created empty (`[]`). The gap patterns need checking against the primary source by the owner or a lawyer. Until then the gap check reports nothing.
- **CABA KB**: `codigo_fiscal_sellos.json` gained `kind: "tax"` and `params` (the numbers are taken from the text of the same record, noted in `note`). The `sellos-locacion` record has no `params` and is marked `pending`.
- **Smoke test** of the real application: `health` → 200, `kb_records: 7`; `POST /v1/reviews` on `locacion_2026_synthetic.docx` → 503 `LLM_UNAVAILABLE` in about 10 s (no provider key, no report returned). A full analysis with the model requires `ANTHROPIC_API_KEY`.
- **Defect found and fixed**: concurrent `encode` calls on one torch model from the analysis threads crashed the process (exit code 139, no traceback). Fixed: loading and `encode` run under a lock in `src/kb/embedder.py`; tests added (`test_concurrent_first_use_loads_the_model_once`, `test_concurrent_encoding_never_overlaps_inside_the_model`). The contract tests did not catch this, because the model in them was loaded before the threads started.
- **CI (T063)**: `HF_HUB_OFFLINE=1` was removed from `.github/workflows/ci.yml`, and a cache for `~/.cache/huggingface` was added (key `hf-intfloat-multilingual-e5-large-v1`); the timeout is 45 min. The first run downloads the model (about 2.2 GB) and the Linux torch wheels (the CUDA wheels are large). Not yet verified on a GitHub runner.
- **T065/T066 — not fully done**: the full quickstart run and the 60-second measurement require a real provider key and real model calls.
- **T067 (AC9, progress indicator)**: the owner has not decided; there is no status endpoint.
- **T069 / T070 — production blockers** (see above): provider terms and verification of the `verbatim: false` texts.
- **Formatting**: `ruff format` reformatted the files in `src/` and `tests/`; behavior did not change.
