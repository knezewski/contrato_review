"""Analysis of one clause through the generative model (T5; spec §3, AC7, AC10, AC14; R8).

The model receives only the clause text and the norms found for it (spec §4).
The response is checked against the schema and the rule «references ⊆ norms found» (constitution I).
Retries: up to `max_attempts` attempts per clause, for both provider failures and invalid responses.
Outcome after the last attempt:
- last error is a provider failure → LLMUnavailable (503);
- last error is an invalid response → LLMInvalidOutput (502).
Pauses between retries are made by the provider client (it knows what a network failure is); here retries are immediate.

A clause without norms is not sent to the model; the status `no_norm` is returned (AC7).
"""

from __future__ import annotations

from src.ingest.split import Clause
from src.report.model import ClauseReview, Finding, ensure_refs_allowed
from src.retrieval.retrieve import RetrievedNorm
from src.review.errors import LLMInvalidOutput, LLMProviderError, LLMUnavailable
from src.review.schema import ClauseReviewOutput

NO_NORM_TEXT = "No se encontró norma aplicable en la base de conocimiento para este punto. Revisión manual."


def review_clause(
    clause: Clause,
    norms: list[RetrievedNorm],
    llm,
    *,
    contract_type: str,
    threshold: float,
    max_attempts: int,
) -> ClauseReview:
    best_score = max((n.score for n in norms), default=None)
    low_confidence = best_score is None or best_score < threshold

    if not norms:
        status = Finding(
            type="no_norm",
            level="low",
            explanation_es=NO_NORM_TEXT,
            no_norm_found=True,
            needs_manual_review=True,
        )
        return ClauseReview(
            clause_id=clause.clause_id,
            marker=clause.marker,
            heading=clause.heading,
            findings=[status],
            best_score=None,
            needs_manual_review=True,
            retrieved_count=0,
        )

    allowed = {n.id for n in norms}
    last_error: Exception | None = None
    for _attempt in range(max_attempts):
        try:
            raw = llm.review_clause(clause.text_es, norms, contract_type)
            parsed = ClauseReviewOutput.model_validate(raw)
            findings = [
                Finding(
                    type=item.type,
                    level=item.level,
                    explanation_es=item.explanation_es,
                    article_refs=item.article_refs,
                    no_norm_found=item.no_norm_found,
                    needs_manual_review=low_confidence,
                )
                for item in parsed.findings
            ]
            for finding in findings:
                ensure_refs_allowed(finding, allowed)
            return ClauseReview(
                clause_id=clause.clause_id,
                marker=clause.marker,
                heading=clause.heading,
                findings=findings,
                best_score=best_score,
                needs_manual_review=low_confidence,
                retrieved_count=len(norms),
            )
        except LLMProviderError as exc:
            last_error = exc
        except ValueError as exc:  # pydantic ValidationError inherits from ValueError
            last_error = exc

    if isinstance(last_error, LLMProviderError):
        raise LLMUnavailable(
            f"clause {clause.clause_id}: provider unavailable"
        ) from last_error
    raise LLMInvalidOutput(
        f"clause {clause.clause_id}: model response failed validation"
    ) from last_error
