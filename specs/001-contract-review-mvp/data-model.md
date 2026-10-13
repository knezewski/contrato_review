# Data Model: Contract Review MVP

Models are pydantic v2 (`src/report/model.py`, `src/review/*`). Contracts are not stored (spec §4). Persistent
stores: Chroma `ar_law` (norms) and SQLite `data/reports.db` (reports without contract text, 30 days, §10).

## 1. Input: ContractDocument (internal, in memory)

| Field | Type | Description |
|-------|------|-------------|
| `source_format` | `"pdf" \| "docx"` | determined from the file signature, not the extension |
| `text_es` | str | extracted Spanish text |
| `page_count` | int | for PDF; 1 for DOCX |
| `needs_ocr` | bool | pages without a text layer |
| `ocr_applied` | bool | OCR was actually run |

Rules: `needs_ocr && !ocr_applied` → error `OCR_UNAVAILABLE` (422). Empty `text_es` → `DOCUMENT_UNREADABLE` (422).

## 2. Contract structure

### Preamble
| Field | Type | Description |
|-------|------|-------------|
| `text_es` | str | text before the first marker; kept as a separate block, not part of the clause analysis |

### Clause
| Field | Type | Description |
|-------|------|-------------|
| `clause_id` | str | `c-01`, `c-02`, … in document order |
| `marker` | str | original marker: `CLÁUSULA PRIMERA`, `ARTÍCULO 3`, `3.` |
| `heading` | str \| null | heading, if any |
| `text_es` | str | full clause text (not trimmed of the marker — kept for quoting) |
| `position` | int | ordinal position in the document |

Rules: `clause_id` is unique within a run; a clause with empty `text_es` is dropped and recorded in `warnings`.
If no markers are found → `NO_CLAUSES_DETECTED` (422), not one "clause for the whole document".

### ContractMeta
| Field | Type | Description |
|-------|------|-------------|
| `contract_type` | `"compraventa" \| "locacion" \| null` | |
| `contract_type_source` | str | text fragment the type was determined from |
| `signing_date` | date \| null | from the text or from the user's request |
| `signing_date_i` | int | `YYYYMMDD`, derived from `signing_date` |
| `signing_date_source` | `"detected" \| "user_provided"` | |

Rules: `contract_type = null` → `CONTRACT_TYPE_UNDETECTED` (422). `signing_date = null` → `SIGNING_DATE_REQUIRED` (422).
If the request supplies a date and the text contains a different one, the request's date takes priority and the conflict is recorded in `warnings`.

## 3. Norms (KB)

### LegalNorm (Chroma record, metadata + document)
| Field | Type in Chroma | Description |
|-------|----------------|-------------|
| `id` | str | `{regime}-{article}`, for example `DNU 70/2023-1198`, `Ley 27.551-1198` (constitution: changing the scheme is a breaking change) |
| `jurisdiction` | str | `nacional` \| `CABA` |
| `contract_type` | str | `compraventa` \| `locacion` \| `all` |
| `regime` | str | `Ley 27.551`, `DNU 70/2023`, CABA regime name |
| `article` | str | article number |
| `title` | str | |
| `valid_from_i` | int | `YYYYMMDD` |
| `valid_to_i` | int | `YYYYMMDD` or `99991231` |
| `source_url` | str | required |
| `verbatim` | bool | quote without changes |
| `kind` | str | `norm` \| `required_element` \| `tax` |
| `element`, `patterns`, `level` | str, list[str], str | only for `required_element` (R10): element name, Spanish regex patterns (case and diacritics ignored), gap level |
| `document` | str | norm text (for embedding — with prefix `passage: `) |

Rules: when indexing, `valid_from`/`valid_to` (ISO or `null`) are converted to `*_i`; `null` in `valid_to` → `99991231`;
any unparseable date → indexing is refused. Records with `verbatim: false` are marked in the report as paraphrases (the `note` field in the source).

### RetrievedNorm (result of Retriever, not stored)
| Field | Type | Description |
|-------|------|-------------|
| `id` | str | reference to LegalNorm.id |
| `jurisdiction`, `regime`, `article`, `source_url`, `verbatim`, `text` | — | from metadata |
| `score` | float | `1 − distance`, range ~[−1, 1], in practice 0–1 |

## 4. Clause analysis

### Finding
| Field | Type | Description |
|-------|------|-------------|
| `type` | `"risk" \| "gap" \| "mismatch" \| "no_norm"` | risk / gap / mismatch against a norm; `no_norm` is the status "no applicable norm found" (AC7), not a legal conclusion |
| `level` | `"low" \| "medium" \| "high"` | level |
| `explanation_es` | str | explanation in Spanish (the language-neutral core of the report) |
| `article_refs` | list[str] | norm IDs from RetrievedNorm |
| `no_norm_found` | bool | `true` if no applicable norm was found (AC7) |
| `source` | `"llm" \| "heuristic"` | where the finding came from; `heuristic` is the gap check (R10) |
| `needs_manual_review` | bool | `true` for all `heuristic` findings; for `llm` — taken from `ClauseReview` |
| `searched_patterns` | list[str] | for a `heuristic` gap: the patterns that were searched (visible to the reviewer) |

Validation (constitution principle I; implemented in `Finding` in `src/report/model.py`):
- `article_refs` ⊆ `{n.id for n in the clause's retrieved norms}` — checked during analysis (`ensure_refs_allowed`);
- for `type ∈ {risk, gap, mismatch}` exactly one of two holds: either `article_refs` is non-empty and `no_norm_found = false`,
  or `article_refs = []` and `no_norm_found = true`. Both or neither is an error;
- `type = "no_norm"`: `article_refs = []`, `no_norm_found = true`, `needs_manual_review = true` (set during analysis).
  This is a status, not a claim about the law: a clause with no norms is not sent to the model;
- `source = "heuristic"` is allowed only with `type = "gap"`, `article_refs` = exactly one `required_element` id,
  `needs_manual_review = true`, and a non-empty `searched_patterns`.
A violation → `LLM_INVALID_OUTPUT` (retry, see R8).

The model output (`ClauseReviewOutput`, `src/review/schema.py`) accepts only `risk | gap | mismatch`:
`no_norm` is never produced by the model; the code sets it when no norms exist for a clause.

### ClauseReview
| Field | Type | Description |
|-------|------|-------------|
| `clause_id` | str | |
| `findings` | list[Finding] | an empty list is allowed: "no problems found" |
| `article_refs` | list[str] | union of references across findings |
| `best_score` | float \| null | best retrieval score; null if there are no norms |
| `needs_manual_review` | bool | `best_score < CONFIDENCE_THRESHOLD` or `best_score is null` (AC10) |
| `retrieved_count` | int | |

Rule: `needs_manual_review = true` does not cancel the findings, but it is shown explicitly in the report.

## 5. CABA stamp tax

### StampTaxResult (sellos)
| Field | Type | Description |
|-------|------|-------------|
| `applies` | bool | |
| `payer` | `"buyer" \| "seller" \| "shared" \| "unknown"` | who pays |
| `vivienda_unica_exemption` | bool \| null | |
| `amount_ars` | decimal \| null | only for compraventa; always null for locacion (spec clarification) |
| `rate_status` | `"confirmed" \| "pending"` | for locacion — `pending` until the Ley Tarifaria 2026 is confirmed |
| `article_refs` | list[str] | CABA norm IDs; empty ⇒ `no_norm_found` |
| `no_norm_found` | bool | |
| `contract_type` | `"compraventa" \| "locacion"` | |
| `warnings` | list[str] | reasons the amount was not calculated (for example, no fiscal valuation) |

Rule: `contract_type = locacion` ⇒ `amount_ars = null`, `rate_status = "pending"` (until confirmed).

## 6. Report (language-neutral, `Report`)

| Field | Type | Description |
|-------|------|-------------|
| `report_id` | UUID4 | identifier of the stored report (§10); a bearer identifier, see R14 |
| `schema_version` | str | `1.0` |
| `source_language` | `"es"` | constant |
| `generated_at` | datetime (UTC) | |
| `contract_type` | `"compraventa" \| "locacion"` | |
| `signing_date` | date | |
| `regime` | `{regime, valid_from_i, valid_to_i}` \| null | one regime per contract; `null` if the KB has no national regime for that date (the report says so) |
| `clause_count` | int | |
| `preamble_present` | bool | |
| `clauses` | list[ClauseReview] | in document order |
| `contract_gaps` | list[Finding] | gaps at contract level (R10) |
| `stamp_tax` | StampTaxResult \| null | |
| `summary` | `{risks, gaps, mismatches, manual_review}` (int) | computed from findings |
| `warnings` | list[str] | non-critical notes (date conflict, ambiguity) |
| `disclaimer_key` | `"informational_v1"` | key of the fixed disclaimer text |

Invariant: `Report` contains no contract text. A clause in the report is represented by `clause_id`, `marker`, `heading`,
and findings; the clause's `text_es` is not part of `Report`.

## 7. Report in a language (`RenderedReport`, output of `render`)

| Field | Type | Description |
|-------|------|-------------|
| `lang` | `"es" \| "en" \| "ru"` | |
| `disclaimer` | str | fixed text from `report/i18n/` in `lang`; for `es` — the original |
| `title`, `labels` | str | headings from i18n |
| `clauses` | list[{clause_id, marker, explanation, finding_types, article_refs}] | `explanation` — the translation of `explanation_es` |
| `legal_terms` | dict | Spanish term → translation, shown in brackets in the text: `arrendamiento (аренда)` |
| `source_language` | `"es"` | |

Rule: every render contains `disclaimer` (test for all `lang`). For `lang="es"` no translation is called.

## 8. Configuration (`config.py`, pydantic-settings)

| Key | Default | Purpose |
|-----|---------|---------|
| `RETRIEVAL_K` | 5 | norms per clause |
| `CONFIDENCE_THRESHOLD` | 0.3 | manual review (AC10) |
| `EMBED_MODEL` | `intfloat/multilingual-e5-large` | |
| `CHROMA_PATH` | `data/chroma` | |
| `CHROMA_COLLECTION` | `ar_law` | |
| `LLM_PROVIDER` | `anthropic` | |
| `LLM_MODEL` | `claude-sonnet-5-5` | |
| `LLM_MAX_ATTEMPTS` | 3 | 1 + 2 retries (R8) |
| `LLM_TIMEOUT_S` | 30 | |
| `LLM_CONCURRENCY` | 5 | parallel clauses (R9) |
| `ANTHROPIC_API_KEY` | — | **secret**, only from `.env`, never logged |
| `OCR_ENABLED` | false | OCR fallback (R11) |
| `OCR_LANG` | `spa` | |
| `MAX_UPLOAD_MB` | 10 | file size limit |
| `REPORTS_DB_PATH` | `data/reports.db` | SQLite with reports (§10) |
| `REPORT_RETENTION_DAYS` | 30 | report retention period (AC15) |

## 9. Review run states

A run has no persisted state until the report is produced. Internal stages and their outcomes:

```
RECEIVED → EXTRACTED → SPLIT → META_OK → RETRIEVED → REVIEWED → REPORTED → STORED → (response) → BUFFERS_RELEASED
              │           │        │                     │
              ▼           ▼        ▼                     ▼
        ERR_UNREADABLE  ERR_NO_CLAUSES  ERR_TYPE / ERR_DATE_REQUIRED   ERR_LLM (any clause)
              (any ERR → HTTP error, no report is produced)
```

`BUFFERS_RELEASED` runs in `finally` for any outcome: the file buffer and `text_es` are removed.
`STORED` — a `StoredReport` record in `reports.db`; a write failure → HTTP 500 `REPORT_STORE_FAILED`, and the report is not returned
(a report that was not saved is not handed out, so the client never receives a `report_id` that does not exist).

## 10. StoredReport (SQLite `data/reports.db`)

| Field | Type | Description |
|-------|------|-------------|
| `report_id` | TEXT PK | UUID4 |
| `created_at` | TEXT | UTC ISO-8601, time of generation |
| `expires_at` | TEXT | `created_at + 30 days` (`REPORT_RETENTION_DAYS = 30`) |
| `report_json` | TEXT | serialized `Report` (§6); no contract text |

Rules:
- Read: `WHERE report_id = ? AND expires_at > now`; otherwise 404 `REPORT_NOT_FOUND`.
- Cleanup: `DELETE WHERE expires_at <= now` at startup and before every read/write.
- If the `schema_version` inside `report_json` does not match on read → 404 (no migration in the MVP).
