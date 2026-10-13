"""FastAPI application factory (T045).

- create_app(deps=...) — for tests: dependencies are replaced immediately, without lifespan.
- create_app() — for running: dependencies are built at startup from Settings (lifespan), and expired reports are purged.
  Run with: uvicorn src.api.app:app
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api import routes_reports, routes_reviews
from src.api.deps import Deps, build_default_deps
from src.api.errors import ApiError, map_exception
from src.config import Settings
from src.ingest.errors import IngestError
from src.review.errors import LLMProviderError, ReviewError

logger = logging.getLogger("contrato_review")


def _error_body(error: ApiError, request_id: str) -> dict:
    return {
        "error": {
            "code": error.code,
            "message": error.message,
            "message_en": error.message_en,
            "request_id": request_id,
        }
    }


def create_app(deps: Deps | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if deps is None:
            app.state.deps = build_default_deps(Settings())
        app.state.deps.report_store.purge_expired()
        yield

    app = FastAPI(title="Contrato Review", version="0.1.0", lifespan=lifespan)
    if deps is not None:
        app.state.deps = deps

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        return await call_next(request)

    async def _handle(request: Request, exc: Exception):
        mapped = map_exception(exc)
        if mapped is None:
            raise exc
        request_id = getattr(request.state, "request_id", "")
        logger.info(
            "error_code=%s request_id=%s status=%s",
            mapped.code,
            request_id,
            mapped.status,
        )
        return JSONResponse(
            status_code=mapped.status, content=_error_body(mapped, request_id)
        )

    async def _handle_provider(request: Request, exc: LLMProviderError):
        return await _handle(request, exc)

    app.add_exception_handler(ApiError, _handle)
    app.add_exception_handler(IngestError, _handle)
    app.add_exception_handler(ReviewError, _handle)
    app.add_exception_handler(LLMProviderError, _handle_provider)

    app.include_router(routes_reviews.router)
    app.include_router(routes_reports.router)

    @app.get("/v1/health")
    async def health(request: Request):
        current: Deps = request.app.state.deps
        return {
            "status": "ok",
            "kb_records": current.kb.count() if hasattr(current.kb, "count") else None,
            "chroma_collection": current.settings.chroma_collection,
            "embed_model": current.settings.embed_model,
            "stored_reports": current.report_store.count(),
        }

    return app


app = create_app()
