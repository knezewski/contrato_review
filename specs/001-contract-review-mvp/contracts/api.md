# API Contract: Contract Review (FastAPI)

Base path: `/v1`. Format: JSON; uploads — `multipart/form-data`. All dates in the API are ISO `YYYY-MM-DD`
(internal `*_i` values never appear in responses). Authentication is not implemented in the MVP: the service runs only in
the local/pilot environment. Under constitution 2.2.0 (principle V), authentication is required before any external access (R14).

Schemas — see [data-model.md](../data-model.md). Only the fields important to the client are listed below.

## 1. POST /v1/reviews — upload and review

A synchronous run of the full pipeline. Target: 95% of runs for ≤ 10 clauses finish in < 60 s (spec §4).

**Request** — `multipart/form-data`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file (`.pdf`, `.docx`) | yes | contract, up to `MAX_UPLOAD_MB` |
| `signing_date` | string `YYYY-MM-DD` | no | resubmitted if auto-detection failed (AC13); takes priority over the date in the text |
| `lang` | `es` \| `en` \| `ru` | no, default `es` | language of the `rendered` field in the response; for `es` no translation is run |

**Response 200** — `application/json`:

```json
{
  "report_id": "7d1c9a2e-3b4f-4e8a-9c1d-2a5f6b7c8d9e",
  "expires_at": "2026-11-12T10:00:00Z",
  "report": { "...": "Report (data-model §6)" },
  "rendered": { "...": "RenderedReport (data-model §7), always present" },
  "lang": "es"
}
```

`report` is always in Spanish (the language-neutral core). `rendered` is the same content in `lang`. Both fields contain
the disclaimer (AC11). The report is stored on the server until `expires_at` (30 days, AC15); it can be fetched in another
language by `report_id` via §2. The contract text is not stored.

**Errors** (the error body uses the single format in §4; no report is returned):

| HTTP | code | When |
|------|------|------|
| 415 | `UNSUPPORTED_FORMAT` | not a PDF/DOCX by signature |
| 413 | `FILE_TOO_LARGE` | larger than `MAX_UPLOAD_MB` |
| 422 | `DOCUMENT_UNREADABLE` | text not extracted / damaged file (AC12) |
| 422 | `OCR_UNAVAILABLE` | scan without a text layer; OCR is off or unavailable (AC12) |
| 422 | `NO_CLAUSES_DETECTED` | no CLÁUSULA/ARTÍCULO/numbering marker found |
| 422 | `CONTRACT_TYPE_UNDETECTED` | type not determined (compraventa / locación) |
| 422 | `SIGNING_DATE_REQUIRED` | date not found; repeat the request with `signing_date` (AC13) |
| 422 | `SIGNING_DATE_INVALID` | `signing_date` is malformed or in the future |
| 503 | `LLM_UNAVAILABLE` | provider unavailable after retries (AC14) |
| 500 | `REPORT_STORE_FAILED` | the report could not be saved; the report is not returned |
| 502 | `LLM_INVALID_OUTPUT` | model response failed validation after retries (R8) |
| 422 | `LANG_UNSUPPORTED` | `lang` outside `es/en/ru` |

On 503 the client repeats the whole request (the file is uploaded again: the contract text is not kept on the server).

## 2. GET /v1/reports/{report_id}?lang=es|en|ru — report by identifier

Returns the stored report in the requested language (AC16). The analysis is not re-run; the contract text is not needed.

**Path**: `report_id` — the UUID4 from the §1 response.
**Query**: `lang` — `es` (default), `en`, `ru`.

**Response 200**: `RenderedReport` (data-model §7) with the fields `report_id`, `expires_at`, `lang`.

**Errors**:

| HTTP | code | When |
|------|------|------|
| 404 | `REPORT_NOT_FOUND` | does not exist, the 30-day period has expired, or it was deleted — no distinction (AC15) |
| 422 | `LANG_UNSUPPORTED` | `lang` outside `es/en/ru` |
| 503 | `LLM_UNAVAILABLE` | translation failed after retries; no partial translation is returned |

Notes:
- For `lang = es` no translation is run; the response is built locally from the stored report.
- `report_id` is a bearer identifier (R14): only its hash prefix is written to the logs, and the endpoint is masked in access logs that record URLs.
- The `Cache-Control: no-store` header on the response is required.

## 3. GET /v1/health

**Response 200**: `{"status": "ok", "kb_records": <int>, "chroma_collection": "ar_law", "embed_model": "...", "stored_reports": <int>}`.
Used to check that the index is ready. It returns no secrets and no file paths.

## 4. Error format

```json
{
  "error": {
    "code": "SIGNING_DATE_REQUIRED",
    "message": "No se pudo detectar la fecha de firma. Indique la fecha (YYYY-MM-DD) y vuelva a enviar el archivo.",
    "message_en": "Signing date could not be detected. Provide it as signing_date (YYYY-MM-DD) and resubmit.",
    "request_id": "2f7c…"
  }
}
```

- `code` — the stable machine-readable code from the tables above.
- `message` — Spanish (the document's language); `message_en` — English. Messages never contain contract text.
- `request_id` — for correlation with the logs (logs contain no contract text; see data-model config and R13).

## 5. Behavior common to all endpoints

- No partial reports: when a stage fails, the body never contains a `report`.
- The uploaded file and `text_es` are deleted in `finally` before the response is sent.
- Only the language-neutral `Report` (without contract text) is stored, for 30 days (R14, data-model §10).
- Contract texts and LLM responses are not logged; `request_id`, stages, durations, error codes, `clause_id`, model, and token counts are logged.
- External LLM calls carry only one clause (plus the norms found for it), and only for translation they carry `explanation_es` and article IDs.
  The gap check (R10) runs locally and makes no external calls.
