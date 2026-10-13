"""Error contract of POST /v1/reviews (contracts/api.md §1, §4). No partial reports."""

from fastapi.testclient import TestClient

from src.api.app import create_app
from tests.contract.conftest import FailingLLM


def _post(deps, filename, data, **form):
    client = TestClient(create_app(deps=deps))
    return client.post("/v1/reviews", files={"file": (filename, data)}, data=form)


def _assert_error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert "report" not in body
    assert body["error"]["code"] == code
    assert body["error"]["message"] and body["error"]["message_en"]
    assert body["error"]["request_id"]


def test_unsupported_format_is_415(make_deps):
    response = _post(make_deps(), "README.md", b"# plain text")
    _assert_error(response, 415, "UNSUPPORTED_FORMAT")


def test_file_over_limit_is_413(make_deps, fixture_bytes):
    response = _post(
        make_deps(max_upload_mb=0),
        "locacion.docx",
        fixture_bytes("locacion_2026_synthetic.docx"),
    )
    _assert_error(response, 413, "FILE_TOO_LARGE")


def test_unreadable_pdf_is_422(make_deps, fixture_bytes):
    response = _post(make_deps(), "roto.pdf", fixture_bytes("unreadable_synthetic.pdf"))
    _assert_error(response, 422, "DOCUMENT_UNREADABLE")


def test_scan_without_ocr_is_422(make_deps, fixture_bytes):
    response = _post(
        make_deps(ocr_enabled=False),
        "scan.pdf",
        fixture_bytes("scan_no_text_synthetic.pdf"),
    )
    _assert_error(response, 422, "OCR_UNAVAILABLE")


def test_no_clause_markers_is_422(make_deps, fixture_bytes):
    response = _post(
        make_deps(), "libre.docx", fixture_bytes("no_clauses_synthetic.docx")
    )
    _assert_error(response, 422, "NO_CLAUSES_DETECTED")


def test_missing_signing_date_is_422_and_can_be_supplied(make_deps, fixture_bytes):
    deps = make_deps()
    response = _post(deps, "sin_fecha.docx", fixture_bytes("no_date_synthetic.docx"))
    _assert_error(response, 422, "SIGNING_DATE_REQUIRED")

    response = _post(
        deps,
        "sin_fecha.docx",
        fixture_bytes("no_date_synthetic.docx"),
        signing_date="2025-06-01",
    )
    assert response.status_code == 200, response.text


def test_invalid_signing_date_is_422(make_deps, fixture_bytes):
    response = _post(
        make_deps(),
        "x.docx",
        fixture_bytes("locacion_2026_synthetic.docx"),
        signing_date="2026-02-30",
    )
    _assert_error(response, 422, "SIGNING_DATE_INVALID")


def test_future_signing_date_is_422(make_deps, fixture_bytes):
    response = _post(
        make_deps(),
        "x.docx",
        fixture_bytes("locacion_2026_synthetic.docx"),
        signing_date="2999-01-01",
    )
    _assert_error(response, 422, "SIGNING_DATE_INVALID")


def test_unsupported_language_is_422(make_deps, fixture_bytes):
    response = _post(
        make_deps(), "x.docx", fixture_bytes("locacion_2026_synthetic.docx"), lang="fr"
    )
    _assert_error(response, 422, "LANG_UNSUPPORTED")


def test_provider_outage_is_503_without_report(make_deps, fixture_bytes):
    response = _post(
        make_deps(llm=FailingLLM()),
        "x.docx",
        fixture_bytes("locacion_2026_synthetic.docx"),
    )
    _assert_error(response, 503, "LLM_UNAVAILABLE")
