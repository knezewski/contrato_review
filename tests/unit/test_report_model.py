from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.report.model import (
    ClauseReview,
    Finding,
    Report,
    StampTaxResult,
    ensure_refs_allowed,
)


def _finding(**overrides):
    base = {
        "type": "risk",
        "level": "high",
        "explanation_es": "Riesgo.",
        "article_refs": ["DNU 70/2023-1198"],
    }
    base.update(overrides)
    return Finding(**base)


def test_finding_with_reference_is_valid():
    assert _finding().no_norm_found is False


def test_finding_without_reference_must_say_no_norm_found():
    with pytest.raises(ValidationError):
        _finding(article_refs=[], no_norm_found=False)
    assert _finding(article_refs=[], no_norm_found=True).article_refs == []


def test_finding_with_reference_cannot_claim_no_norm():
    with pytest.raises(ValidationError):
        _finding(no_norm_found=True)


def test_no_norm_status_finding_has_no_references():
    finding = Finding(
        type="no_norm", level="low", explanation_es="Sin norma.", no_norm_found=True
    )
    assert finding.article_refs == []
    with pytest.raises(ValidationError):
        Finding(
            type="no_norm",
            level="low",
            explanation_es="Sin norma.",
            article_refs=["x"],
            no_norm_found=True,
        )


def test_heuristic_gap_rules():
    gap = Finding(
        type="gap",
        level="high",
        explanation_es="Falta el precio.",
        article_refs=["DNU 70/2023-1198"],
        source="heuristic",
        needs_manual_review=True,
        searched_patterns=["precio", "canon"],
    )
    assert gap.source == "heuristic"

    with pytest.raises(ValidationError):  # only gap
        Finding(
            type="risk",
            level="high",
            explanation_es="x",
            article_refs=["a"],
            source="heuristic",
            needs_manual_review=True,
            searched_patterns=["p"],
        )
    with pytest.raises(ValidationError):  # manual review is mandatory
        Finding(
            type="gap",
            level="high",
            explanation_es="x",
            article_refs=["a"],
            source="heuristic",
            needs_manual_review=False,
            searched_patterns=["p"],
        )
    with pytest.raises(ValidationError):  # the list of patterns is mandatory
        Finding(
            type="gap",
            level="high",
            explanation_es="x",
            article_refs=["a"],
            source="heuristic",
            needs_manual_review=True,
            searched_patterns=[],
        )
    with pytest.raises(ValidationError):  # exactly one reference
        Finding(
            type="gap",
            level="high",
            explanation_es="x",
            article_refs=["a", "b"],
            source="heuristic",
            needs_manual_review=True,
            searched_patterns=["p"],
        )


def test_references_must_be_among_retrieved_norms():
    ensure_refs_allowed(_finding(), {"DNU 70/2023-1198", "Ley 27.551-1198"})
    with pytest.raises(ValueError):
        ensure_refs_allowed(
            _finding(article_refs=["inventada-1"]), {"DNU 70/2023-1198"}
        )


def test_clause_review_exposes_union_of_references():
    review = ClauseReview(
        clause_id="c-01",
        marker="CLÁUSULA PRIMERA",
        heading=None,
        findings=[_finding(article_refs=["a"]), _finding(article_refs=["b"])],
        best_score=0.8,
        needs_manual_review=False,
        retrieved_count=5,
    )
    assert review.article_refs == ["a", "b"]


def test_locacion_stamp_tax_has_no_amount_and_is_pending():
    ok = StampTaxResult(
        contract_type="locacion",
        applies=True,
        payer="unknown",
        vivienda_unica_exemption=None,
        amount_ars=None,
        rate_status="pending",
        article_refs=["sellos-locacion"],
        no_norm_found=False,
    )
    assert ok.amount_ars is None
    with pytest.raises(ValidationError):
        StampTaxResult(
            contract_type="locacion",
            applies=True,
            payer="buyer",
            vivienda_unica_exemption=None,
            amount_ars=Decimal(100),
            rate_status="pending",
            article_refs=["x"],
            no_norm_found=False,
        )
    with pytest.raises(ValidationError):
        StampTaxResult(
            contract_type="locacion",
            applies=True,
            payer="buyer",
            vivienda_unica_exemption=None,
            amount_ars=None,
            rate_status="confirmed",
            article_refs=["x"],
            no_norm_found=False,
        )


def test_report_has_fixed_schema_and_disclaimer_key():
    report = Report(
        contract_type="locacion",
        signing_date="2026-03-15",
        regime={
            "regime": "DNU 70/2023",
            "valid_from_i": 20231230,
            "valid_to_i": 99991231,
        },
        clause_count=0,
        preamble_present=True,
        clauses=[],
        contract_gaps=[],
        stamp_tax=None,
        summary={"risks": 0, "gaps": 0, "mismatches": 0, "manual_review": 0},
        warnings=[],
        generated_at=datetime.now(UTC),
    )
    assert report.schema_version == "1.0"
    assert report.source_language == "es"
    assert report.disclaimer_key == "informational_v1"
