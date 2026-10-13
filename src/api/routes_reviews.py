"""POST /v1/reviews — contract upload and analysis (contracts/api.md §1).

Order: analysis → translation (if needed) → report storage → response. If any step fails,
the report is neither stored nor returned (AC12, AC14). The file buffer is removed in finally.
"""

from __future__ import annotations

import time
import uuid
from datetime import date

from fastapi import APIRouter, File, Form, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from src.api.deps import Deps
from src.api.errors import api_error
from src.api.logging import log_event, report_ref
from src.ingest.errors import OcrUnavailable
from src.ingest.extract import extract
from src.ingest.meta import detect_meta
from src.ingest.ocr import ocr_pdf
from src.ingest.split import split_contract
from src.report.model import Report
from src.report.render import SUPPORTED, render_report
from src.review.orchestrator import run_review

router = APIRouter()
MB = 1024 * 1024


def _parse_signing_date(value: str | None) -> date | None:
    if value is None or value.strip() == "":
        return None
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError as exc:
        raise api_error("SIGNING_DATE_INVALID") from exc
    if parsed > date.today():
        raise api_error("SIGNING_DATE_INVALID")
    return parsed


def _run_pipeline(data: bytes, user_date: date | None, deps: Deps) -> Report:
    document = extract(data)
    text = document.text_es
    if document.needs_ocr:
        if not deps.settings.ocr_enabled:
            raise OcrUnavailable("scan without a text layer, OCR is disabled")
        text = ocr_pdf(data, deps.settings.ocr_lang)
    split = split_contract(text)
    meta = detect_meta(text, user_date)
    return run_review(
        split=split,
        meta=meta,
        retriever=deps.retriever,
        llm=deps.llm,
        kb=deps.kb,
        settings=deps.settings,
        full_text=text,
    )


@router.post("/v1/reviews")
async def create_review(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008 — standard FastAPI pattern
    signing_date: str | None = Form(None),
    lang: str = Form("es"),
):
    deps: Deps = request.app.state.deps
    request_id = request.state.request_id
    if lang not in SUPPORTED:
        raise api_error("LANG_UNSUPPORTED")
    user_date = _parse_signing_date(signing_date)

    limit = deps.settings.max_upload_mb * MB
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise api_error("FILE_TOO_LARGE")

    started = time.perf_counter()
    try:
        report = await run_in_threadpool(_run_pipeline, data, user_date, deps)
    finally:
        del data

    report_json = report.model_dump(mode="json")
    rendered = await run_in_threadpool(
        render_report, report_json, lang, deps.translator, deps.glossary
    )

    report_id = str(uuid.uuid4())
    try:
        expires = deps.report_store.save(report_id, report_json)
    except Exception as exc:
        raise api_error("REPORT_STORE_FAILED") from exc

    log_event(
        request_id=request_id,
        stage="review",
        duration_ms=int((time.perf_counter() - started) * 1000),
        clauses=report.clause_count,
        model=deps.settings.llm_model,
        report_ref=report_ref(report_id),
        status=200,
    )
    return {
        "report_id": report_id,
        "expires_at": expires.isoformat(),
        "lang": lang,
        "report": report_json,
        "rendered": rendered,
    }
