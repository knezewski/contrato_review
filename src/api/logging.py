"""Run log without contract text (spec §4, constitution V, research.md R13).

The log contains only: request_id, stage, duration, error code, clause count, model.
Contract, clause and model response text is never logged. The report identifier appears only as a hash prefix (R14).
"""

from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger("contrato_review")

ALLOWED_FIELDS = {
    "request_id",
    "stage",
    "duration_ms",
    "error_code",
    "clauses",
    "model",
    "status",
    "report_ref",
}


def log_event(**fields) -> None:
    unknown = set(fields) - ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"log fields outside the allowed set: {sorted(unknown)}")
    logger.info(" ".join(f"{key}={value}" for key, value in fields.items()))


def report_ref(report_id: str) -> str:
    return hashlib.sha256(report_id.encode()).hexdigest()[:12]
