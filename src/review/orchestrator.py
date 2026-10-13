"""Contract analysis pipeline: regime → clauses (in parallel) → gaps → taxes → report (T5).

Outcome: either a complete Report or an exception. No partial report is returned (AC12, AC14).
Contract text lives in memory for the duration of the call; the caller (API) releases the buffers.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from src.config import Settings
from src.ingest.errors import ContractTypeUndetected, SigningDateRequired
from src.ingest.meta import ContractMeta
from src.ingest.split import SplitResult
from src.report.model import ClauseReview, RegimeInfo, Report
from src.retrieval.retrieve import RetrievalQuery
from src.review.clause_review import review_clause
from src.review.gaps import find_gaps
from src.review.regime import select_regime
from src.review.stamp_tax import compute_stamp_tax, extract_facts


def _date_i(value) -> int:
    return value.year * 10000 + value.month * 100 + value.day


def run_review(
    *,
    split: SplitResult,
    meta: ContractMeta,
    retriever,
    llm,
    kb,
    settings: Settings,
    full_text: str,
) -> Report:
    if meta.signing_date is None:
        raise SigningDateRequired("signing date not provided")
    if meta.contract_type is None:
        raise ContractTypeUndetected("contract type not determined")

    contract_type = meta.contract_type
    day = _date_i(meta.signing_date)
    regime = select_regime(
        meta.signing_date, contract_type, kb.national_regime_records(contract_type)
    )

    def _review(clause):
        query = RetrievalQuery(
            text=clause.text_es,
            signing_date_i=day,
            contract_type=contract_type,
            regime=regime.regime,
            k=settings.retrieval_k,
        )
        norms = retriever.search(query)
        return review_clause(
            clause,
            norms,
            llm,
            contract_type=contract_type,
            threshold=settings.confidence_threshold,
            max_attempts=settings.llm_max_attempts,
        )

    with ThreadPoolExecutor(max_workers=max(1, settings.llm_concurrency)) as pool:
        clause_reviews: list[ClauseReview] = list(pool.map(_review, split.clauses))

    gaps = find_gaps(full_text, kb.required_elements(contract_type, day))
    facts = extract_facts(full_text)
    stamp = compute_stamp_tax(contract_type, facts, kb.tax_records(contract_type, day))

    all_findings = [f for review in clause_reviews for f in review.findings]
    summary = {
        "risks": sum(1 for f in all_findings if f.type == "risk"),
        "gaps": sum(1 for f in all_findings if f.type == "gap") + len(gaps),
        "mismatches": sum(1 for f in all_findings if f.type == "mismatch"),
        "manual_review": sum(1 for r in clause_reviews if r.needs_manual_review)
        + len(gaps),
    }
    warnings = list(meta.warnings) + list(split.warnings) + list(stamp.warnings)

    return Report(
        generated_at=datetime.now(UTC),
        contract_type=contract_type,
        signing_date=meta.signing_date,
        regime=(
            RegimeInfo(
                regime=regime.regime,
                valid_from_i=regime.valid_from_i,
                valid_to_i=regime.valid_to_i,
            )
            if regime.regime
            else None
        ),
        clause_count=len(clause_reviews),
        preamble_present=bool(split.preamble),
        clauses=clause_reviews,
        contract_gaps=gaps,
        stamp_tax=stamp,
        summary=summary,
        warnings=warnings,
    )
