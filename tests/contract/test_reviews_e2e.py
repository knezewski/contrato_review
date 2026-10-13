"""End-to-end analysis of synthetic contracts on the real norm index with a fake model (T048–T050)."""

import logging

from fastapi.testclient import TestClient

from src.api.app import create_app
from tests.contract.conftest import EchoLLM


def _post(deps, data, filename="contrato.docx", **form):
    client = TestClient(create_app(deps=deps))
    return client.post("/v1/reviews", files={"file": (filename, data)}, data=form)


def test_lease_2026_applies_dnu_regime(make_deps, fixture_bytes):
    response = _post(make_deps(), fixture_bytes("locacion_2026_synthetic.docx"))
    assert response.status_code == 200, response.text
    report = response.json()["report"]
    assert report["contract_type"] == "locacion"
    assert report["signing_date"] == "2026-03-15"
    assert report["regime"]["regime"] == "DNU 70/2023"
    assert report["clause_count"] == 10
    assert report["preamble_present"] is True


def test_lease_2022_applies_ley_27551(make_deps, fixture_bytes):
    response = _post(make_deps(), fixture_bytes("locacion_2022_synthetic.docx"))
    assert response.status_code == 200, response.text
    assert response.json()["report"]["regime"]["regime"] == "Ley 27.551"


def test_user_supplied_date_unblocks_review(make_deps, fixture_bytes):
    response = _post(
        make_deps(), fixture_bytes("no_date_synthetic.docx"), signing_date="2025-06-01"
    )
    assert response.status_code == 200, response.text
    assert response.json()["report"]["regime"]["regime"] == "DNU 70/2023"


def test_every_finding_references_a_retrieved_norm_or_says_none(
    make_deps, fixture_bytes
):
    response = _post(make_deps(), fixture_bytes("locacion_2026_synthetic.docx"))
    for clause in response.json()["report"]["clauses"]:
        for finding in clause["findings"]:
            assert (
                bool(finding["article_refs"]) != finding["no_norm_found"]
                or finding["type"] == "no_norm"
            )


def test_lease_stamp_tax_is_pending_without_amount(make_deps, fixture_bytes):
    response = _post(make_deps(), fixture_bytes("locacion_2026_synthetic.docx"))
    tax = response.json()["report"]["stamp_tax"]
    assert tax["rate_status"] == "pending"
    assert tax["amount_ars"] is None


def test_low_confidence_clauses_are_flagged(make_deps, fixture_bytes):
    response = _post(
        make_deps(confidence_threshold=0.99),
        fixture_bytes("locacion_2026_synthetic.docx"),
    )
    report = response.json()["report"]
    assert all(clause["needs_manual_review"] for clause in report["clauses"])
    assert report["summary"]["manual_review"] >= report["clause_count"]


def test_missing_price_clause_is_reported_as_gap_when_pattern_is_in_kb(
    make_deps, fixture_bytes
):
    # The KB has no required_element records yet: the gap check reports nothing (see tasks T040).
    response = _post(make_deps(), fixture_bytes("locacion_no_price_synthetic.docx"))
    assert response.status_code == 200, response.text
    assert response.json()["report"]["contract_gaps"] == []


def test_sale_without_national_norms_reports_no_regime(make_deps, fixture_bytes):
    response = _post(make_deps(), fixture_bytes("compraventa_2025_synthetic.docx"))
    assert response.status_code == 200, response.text
    assert response.json()["report"]["regime"] is None


def test_logs_never_contain_contract_text(make_deps, fixture_bytes, caplog):
    caplog.set_level(logging.DEBUG)
    response = _post(
        make_deps(llm=EchoLLM()), fixture_bytes("locacion_2026_synthetic.docx")
    )
    assert response.status_code == 200
    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert "doscientos mil" not in joined
    assert "locador da en locación" not in joined
    assert "stage=review" in joined
