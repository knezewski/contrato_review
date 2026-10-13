"""Contract for report storage and retrieval (T053, T060; spec §4, AC15, AC16; R14)."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from src.api.app import create_app
from tests.contract.conftest import EchoLLM, FailingLLM


def _review(client, data, **form):
    return client.post(
        "/v1/reviews", files={"file": ("contrato.docx", data)}, data=form
    )


class BrokenStore:
    def save(self, report_id, report, now=None):
        raise OSError("disco lleno (prueba)")

    def get(self, report_id, now=None):
        return None

    def purge_expired(self, now=None):
        return 0

    def count(self):
        return 0


def test_review_returns_report_id_and_expiry(make_deps, fixture_bytes):
    client = TestClient(create_app(deps=make_deps()))
    response = _review(client, fixture_bytes("locacion_2026_synthetic.docx"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["report_id"]
    assert body["expires_at"]
    assert body["rendered"]["disclaimer"]


def test_stored_report_can_be_fetched_in_another_language(make_deps, fixture_bytes):
    deps = make_deps()
    client = TestClient(create_app(deps=deps))
    report_id = _review(client, fixture_bytes("locacion_2026_synthetic.docx")).json()[
        "report_id"
    ]

    response = client.get(f"/v1/reports/{report_id}", params={"lang": "es"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["report_id"] == report_id
    assert body["lang"] == "es"
    assert body["disclaimer"]
    assert body["regime"]["regime"] == "DNU 70/2023"


def test_get_does_not_rerun_analysis_for_spanish(make_deps, fixture_bytes):
    llm = EchoLLM()
    deps = make_deps(llm=llm)
    client = TestClient(create_app(deps=deps))
    report_id = _review(client, fixture_bytes("locacion_2026_synthetic.docx")).json()[
        "report_id"
    ]
    calls_after_review = llm.calls
    client.get(f"/v1/reports/{report_id}", params={"lang": "es"})
    assert llm.calls == calls_after_review


def test_unknown_report_is_404(make_deps):
    client = TestClient(create_app(deps=make_deps()))
    response = client.get("/v1/reports/00000000-0000-4000-8000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REPORT_NOT_FOUND"


def test_expired_report_gives_the_same_404(make_deps, fixture_bytes):
    deps = make_deps()
    client = TestClient(create_app(deps=deps))
    report_id = _review(client, fixture_bytes("locacion_2026_synthetic.docx")).json()[
        "report_id"
    ]
    later = datetime.now(UTC) + timedelta(days=31)
    deps.report_store.purge_expired(now=later)
    expired = client.get(f"/v1/reports/{report_id}")
    unknown = client.get("/v1/reports/00000000-0000-4000-8000-000000000000")
    assert expired.status_code == unknown.status_code == 404
    assert expired.json()["error"]["code"] == unknown.json()["error"]["code"]


def test_unsupported_language_on_get_is_422(make_deps, fixture_bytes):
    client = TestClient(create_app(deps=make_deps()))
    report_id = _review(client, fixture_bytes("locacion_2026_synthetic.docx")).json()[
        "report_id"
    ]
    response = client.get(f"/v1/reports/{report_id}", params={"lang": "fr"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "LANG_UNSUPPORTED"


def test_store_failure_returns_500_without_report(make_deps, fixture_bytes):
    deps = make_deps()
    deps.report_store = BrokenStore()
    client = TestClient(create_app(deps=deps))
    response = _review(client, fixture_bytes("locacion_2026_synthetic.docx"))
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "REPORT_STORE_FAILED"
    assert "report" not in response.json()


def test_translation_outage_returns_503_and_stores_nothing(make_deps, fixture_bytes):
    deps = make_deps(llm=FailingLLM())
    client = TestClient(create_app(deps=deps))
    response = _review(client, fixture_bytes("locacion_2026_synthetic.docx"), lang="en")
    assert response.status_code == 503
    assert deps.report_store.count() == 0


def test_startup_purges_expired_reports(make_deps, fixture_bytes):
    deps = make_deps()
    client = TestClient(create_app(deps=deps))
    _review(client, fixture_bytes("locacion_2026_synthetic.docx"))
    assert deps.report_store.count() == 1
    deps.report_store.save(
        "viejo", {"schema_version": "1.0"}, now=datetime(2020, 1, 1, tzinfo=UTC)
    )
    with TestClient(create_app(deps=deps)):
        pass
    assert deps.report_store.count() == 1
