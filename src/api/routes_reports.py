"""GET /v1/reports/{report_id}?lang=es|en|ru — a stored report in the requested language (contracts/api.md §2; AC15, AC16).

The analysis is not re-run; for `es` no translation is called. An expired and an unknown id both give the same 404.
The response is not cached (Cache-Control: no-store).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from src.api.deps import Deps
from src.api.errors import api_error
from src.api.logging import log_event, report_ref
from src.report.render import SUPPORTED, render_report

router = APIRouter()


@router.get("/v1/reports/{report_id}")
async def get_report(report_id: str, request: Request, lang: str = "es"):
    deps: Deps = request.app.state.deps
    if lang not in SUPPORTED:
        raise api_error("LANG_UNSUPPORTED")
    found = await run_in_threadpool(deps.report_store.get, report_id)
    if found is None:
        raise api_error("REPORT_NOT_FOUND")
    rendered = await run_in_threadpool(
        render_report, found["report"], lang, deps.translator, deps.glossary
    )
    log_event(
        request_id=request.state.request_id,
        stage="report_get",
        report_ref=report_ref(report_id),
        status=200,
    )
    body = {"report_id": report_id, "expires_at": found["expires_at"], **rendered}
    return JSONResponse(content=body, headers={"Cache-Control": "no-store"})
