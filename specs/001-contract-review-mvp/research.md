# Research: Contract Review MVP

Each decision: **Decision** — what was chosen; **Rationale** — why; **Alternatives** — what was considered.
All NEEDS CLARIFICATION items from plan.md are resolved here.

## R1. Vector store: Chroma now, pgvector in production

**Decision**: Chroma PersistentClient (`data/chroma`), collection `ar_law`, `metadata={"hnsw:space": "cosine"}`.
Access to the store goes only through the `Retriever` interface (see R2).

**Rationale**: a local file store with no separate service, sufficient for dozens to hundreds of norm records;
already chosen in the constitution and the description. Metadata filters (`$and`, `$lte`, `$gte`, `$in`) cover the needed
queries.

**Alternatives**: pgvector now — requires Postgres in the dev environment, premature for the MVP; FAISS — no
metadata filters out of the box.

## R2. Isolating the retrieval interface (for a future pgvector)

**Decision**: `Retriever` takes a `RetrievalQuery` (texts, k, jurisdictions, contract_type, regime, signing_date_i)
and returns `list[RetrievedNorm]` with `score`. Chroma specifics (`where` dictionaries, `distance`) stay inside
`retrieve.py` only. Switching to pgvector means a new implementation of the same class.

**Rationale**: lets the store be replaced without changes in `review/` and `api/`.

**Alternatives**: calling chromadb directly from review — cheaper now, but leaks the abstraction.

## R3. Generative LLM: Anthropic Claude (decision; owner confirmation required)

**Decision**: provider — **Anthropic** (Claude). The model is set in the config `LLM_MODEL`, default `claude-sonnet-5-5`
(faster while keeping quality for clause analysis). A call with structured output (tool use with the JSON schema
`ClauseReviewOutput`), `temperature=0`. One model for both analysis and translation.

**Rationale**: the constitution requires naming the provider in the plan (follow-up to amendment 2026-10-13). The owner
confirmed Anthropic (option 2-B): the provider is recorded in the spec (§8) and in the Principle V amendment.
One provider simplifies checking the privacy and logging requirements. Tool use gives a strictly typed response,
validated by pydantic.

**Conditions before the first real contract** (checklist, not code):
1. Record in the Principle V amendment: provider "Anthropic", model set by configuration.
2. Check and record in the plan the data-retention and training terms for data held by the provider (retention, training
   opt-out for the project's API account); if the terms are not acceptable — a separate amendment or a change of provider.
3. Amendment 2.1.0 is applied in `.specify/memory/constitution.md` (Sync Impact Report and migration note updated).
   Items 1 and 3 are done; item 2 stays open until the first real contract.

**Alternatives**: GPT (OpenAI) — equivalent in function, same constraints, and no approval for it.
Changing the provider means a new `LLMClient` implementation; the data model does not change.

## R4. Dates and the validity-period filter

**Decision**:
- Chroma stores `valid_from_i`, `valid_to_i`, `signing_date_i` as **int YYYYMMDD**.
- An open `valid_to` → `99991231`. Source JSON files keep `valid_to: null` and ISO dates (the constitution requires
  keeping the source and dates); normalization happens in `kb/dates.py` at indexing time (`index` stage).
- Period filter: `{"$and": [{"valid_from_i": {"$lte": D}}, {"valid_to_i": {"$gte": D}}]}`.
- Strings (`""`, `null`) are not allowed in filtered fields; `index` fails if a date cannot be parsed.

**Rationale**: Chroma compares only numbers; `""` breaks comparisons (this is the discrepancy the constitution points to).
Strict validation in `index` catches the error at the input.

**Alternatives**: ISO strings with lexicographic comparison — not reliably supported by `$gte` on Chroma metadata;
post-filtering in Python — possible, but does not return k results within the period.

## R5. Regime selection and signing date

**Decision**:
- The signing date D is taken from `meta.py`. If it is not found or is ambiguous → HTTP 422 `SIGNING_DATE_REQUIRED`;
  the client repeats the request with the field `signing_date` (YYYY-MM-DD). No state is kept on the server (AC13 + spec §4).
- The regime is chosen **once per contract**: `regime.py` looks in the KB for records with the contract's `contract_type`,
  national jurisdiction and `valid_from_i <= D <= valid_to_i`; the regime of those records is used. For D = 2023-12-30 → DNU 70/2023;
  for D = 2022 → Ley 27.551 (from `data/laws/nacional/*.json`, not hard-coded).
- Each clause is then searched with the filter `regime == R` and `jurisdiction ∈ {nacional, CABA}`. CABA records, which have
  no regime of their own, are filtered by the period D only.

**Rationale**: enforces "one regime for the whole contract" from spec §3 and prevents mixing norms from two regimes.

**Alternatives**: choosing a regime per clause — forbidden by the spec.

## R6. Getting a report in a language: GET by report_id (owner decision, spec §4 and AC15–AC16)

**Decision**: `POST /v1/reviews` returns `report_id` and `expires_at`; `GET /v1/reports/{report_id}?lang=es|en|ru`
returns the report in the requested language from the stored language-neutral `Report`. Translation runs on every request
(no translation cache in the MVP — see R14). For `lang=es` the LLM is not called.

**Rationale**: the owner allowed storing the report for 30 days; GET by id is the direct way to fetch the report later and in
another language. Only the language-neutral report without contract text is stored.

**Alternatives**: a stateless `POST /reports/render` with the report in the body — needs no storage, but the client would have to keep
the report; rejected by the owner in favor of storage. A cache of translated versions would speed up repeats but adds a second
persistent copy of the report text; deferred.

## R7. Confidence threshold and k

**Decision**:
- `RETRIEVAL_K = 5` (norms per clause).
- Score = `1 − distance` (in Chroma, for cosine, `distance` = 1 − cosine similarity; verify on the first run with check queries).
- `CONFIDENCE_THRESHOLD = 0.3` on the clause's best score; below it — `needs_manual_review = true` (AC10). The value is
  provisional and is revisited after the first run.
- If retrieval returns 0 norms after filtering → `no_norm_found = true` in findings (AC7).

**Rationale**: values come from the spec; they are configured via `config.py`.

**Alternatives**: a distance threshold without inversion — easy to get the direction wrong; the score is fixed explicitly.

## R8. LLM errors: retries and no partial report

**Decision**: per clause — up to 3 attempts (1 + 2 retries), backoff 1 s and 3 s, request timeout 30 s. If at least
one clause is not analyzed after the retries → the whole run fails with HTTP 503 `LLM_UNAVAILABLE`, and no report is produced
(AC14). Validation errors in the model response (invalid JSON / reference to a norm outside the retrieved set) are treated as
a retry of the same attempt; after they are exhausted they become `LLM_INVALID_OUTPUT`.

**Rationale**: AC14 and "no partial reports" (AC12).

## R9. Performance (≤ 60 s for 10 clauses in 95% of runs)

**Decision**: clauses are processed in parallel with a semaphore `LLM_CONCURRENCY = 5`. The embedder and Chroma are
initialized once at application startup (lifespan). Expected time: embedding 10 queries < 1 s on CPU/MPS;
LLM — 10 calls at ~5–10 s each with concurrency 5 → ~20 s with headroom.

**Note**: the model is not safe for concurrent `encode` calls from several threads (it crashes the process, exit 139).
Inference is therefore serialized inside `E5Embedder`; LLM calls still run in parallel.

**Alternatives**: sequential processing — ~60–100 s, does not meet the target.

## R10. Missing mandatory elements (UC3, AC17) — deterministic check

**Decision**:
- The KB gets records with `kind = "required_element"` (one per element and regime). Fields beyond LegalNorm:
  - `element` — element name (for example "precio", "plazo", "domicilio de las partes");
  - `patterns` — list of Spanish regular expressions (case and diacritics ignored);
  - `level` — `low | medium | high`, the gap level.
  Records are maintained under the constitution: with `source_url` and dates, checked against the source before indexing.
- Algorithm (`review/gaps.py`): take `required_element` records matching the contract's `contract_type` and valid on the
  signing date D. For each record, search for any of its `patterns` in the **full contract text** (preamble + all clauses).
  No match → `Finding(type="gap", source="heuristic", needs_manual_review=true, article_refs=[record id])`.
  Match → nothing is added.
- No external calls. The clause text never leaves the process.
- Failure modes are documented at the top of `gaps.py` (principle IV):
  - false negatives: the element is present but worded differently from the patterns, so a pattern matches unrelated text and
    no gap is raised (the error is toward "no gap");
  - false positives: the element is present but the patterns do not match (for example, it is in an annex or a table) — the gap is
    raised with a manual-review flag, and the reviewer sees `searched_patterns`;
  - `searched_patterns` appear in the report so the reviewer can see what was searched.

**Rationale**: the owner chose "one clause together with the norms found" as the only content of a request to the LLM,
so the completeness check must not send any text outside. The `source="heuristic"` label and `needs_manual_review=true`
prevent a heuristic from being presented as a legal conclusion (principle III).

**Tests**: a set of synthetic contracts with known presence/absence of each element; precision/recall are recorded in the
tasks. Patterns are extended only based on results from such tests.

**Alternatives**: an LLM check over clause headings (rejected: widens what is sent, beyond the owner's choice); not checking
gaps at all (rejected: leaves UC3 unresolved).

## R11. OCR

**Decision**: `extract.py` sets `needs_ocr=true` for pages without a text layer. If `OCR_ENABLED=true` and the system
`tesseract` with language `spa` is available, pages are recognized (`pytesseract`, `pdf2image`). Otherwise the run fails
with HTTP 422 `OCR_UNAVAILABLE` and an instruction (AC12, spec clarifications).

**Rationale**: OCR is an optional fallback (constitution, Technical Constraints).

## R12. Translation (T7)

**Decision**: translation is a separate step in `render.py`. **Only** the fields `explanation_es`, `article_refs`, and short
type labels go to the LLM; the contract text is not sent. Legal terms are kept in Spanish in parentheses according to the glossary
`data/glossary/es_terms.json`. The disclaimer and labels are fixed texts in `report/i18n/` and are not translated by the model.
Check: the disclaimer is present in every render (test).

**Alternatives**: translating everything through the LLM — the model could alter the disclaimer, which violates AC11.

## R14. Report storage: 30 days, SQLite, no contract text

**Decision**:
- Storage is SQLite `data/reports.db` (stdlib `sqlite3`), table `reports(report_id TEXT PK, created_at TEXT, expires_at TEXT, report_json TEXT)`. Dates are UTC ISO.
- Retention: `expires_at = created_at + 30 days`. Expired records are removed at application startup and on every access to the store (`DELETE WHERE expires_at < now`). A request for an expired or unknown `report_id` → 404 `REPORT_NOT_FOUND` (AC15).
- Only the `Report` is stored (data-model §6). The contract's `text_es` is not included. The field `explanation_es` may contain short quotes from a clause: the prompt asks for a paraphrase rather than verbatim copying, and a test checks that long fragments (> 80 consecutive characters) do not appear in `explanation_es`.
- `report_id` is a UUID4 (122 bits of randomness). It is a bearer identifier: anyone who has it can read the report without authentication. For that reason `report_id` is not logged in plain form (only its hash prefix is logged) and is not passed in log URLs.
- Encryption at rest is not done in the MVP; the file `data/reports.db` is in `.gitignore` and has file mode `0600`.
- The `POST /v1/reviews` response contains `report_id` and `expires_at`; the client keeps them itself.

**Rationale**: SQLite needs no separate service and suits a single process. Purging by `expires_at` implements AC15.

**Alternatives**:
- JSON files on disk — harder to purge and to access concurrently.
- Postgres now — excessive for the MVP; when moving to pgvector, reports can move into the same database.
- Field encryption with a key from `.env` — deferred: requires separate key management; to be proposed in the next phase.

**Authentication**: constitution 2.2.0 (principle V) requires authentication before any external access to the service.
The method (API key or session cookie) is chosen in a separate step. Until then the service runs only in the local/pilot
environment, and `report_id` is the only protection.

## R13. Logging and privacy

**Decision**: logs contain request_id, stage, duration, error code, clause id, model, and token count. The contract text, clause
text, and LLM response are never written to the logs. The uploaded file is read from memory (`bytes`) without writing to disk;
after the response is built, the buffers are released with `del` (in `finally`).

**Rationale**: spec §4 and constitution V.
