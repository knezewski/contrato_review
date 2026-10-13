import threading
import time
from datetime import date

import pytest

from src.config import Settings
from src.ingest.errors import ContractTypeUndetected, SigningDateRequired
from src.ingest.meta import ContractMeta
from src.ingest.split import split_contract
from src.retrieval.retrieve import RetrievedNorm
from src.review.errors import LLMUnavailable
from src.review.orchestrator import run_review

TEXT = """CONTRATO DE LOCACIÓN DE VIVIENDA

CLÁUSULA PRIMERA — OBJETO
El locador da en locación el inmueble. Domicilio: calle 1.

CLÁUSULA SEGUNDA — PRECIO
El precio mensual es de $200.000.
"""


class FakeKb:
    def national_regime_records(self, contract_type):
        return [
            {
                "jurisdiction": "nacional",
                "contract_type": "locacion",
                "regime": "Ley 27.551",
                "valid_from_i": 20200701,
                "valid_to_i": 20231229,
            },
            {
                "jurisdiction": "nacional",
                "contract_type": "locacion",
                "regime": "DNU 70/2023",
                "valid_from_i": 20231230,
                "valid_to_i": 99991231,
            },
        ]

    def required_elements(self, contract_type, signing_date_i):
        return [
            {
                "id": "DNU 70/2023-1197",
                "element": "precio",
                "level": "high",
                "patterns": ["precio", "canon"],
            }
        ]

    def tax_records(self, contract_type, signing_date_i):
        return []


class FakeRetriever:
    def __init__(self):
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        return [
            RetrievedNorm(
                id="DNU 70/2023-1198",
                jurisdiction="nacional",
                regime="DNU 70/2023",
                article="1198",
                title="Plazo",
                source_url="https://example.test",
                verbatim=False,
                text="Texto.",
                kind="norm",
                score=0.9,
            )
        ]


class FakeLLM:
    def __init__(self, fail=False, delay=0.0):
        self.fail = fail
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def review_clause(self, clause_text, norms, contract_type):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(self.delay)
            if self.fail and "PRECIO" in clause_text:
                from src.review.errors import LLMProviderError

                raise LLMProviderError("boom")
            return {
                "findings": [
                    {
                        "type": "risk",
                        "level": "low",
                        "explanation_es": "Revisar.",
                        "article_refs": ["DNU 70/2023-1198"],
                        "no_norm_found": False,
                    }
                ]
            }
        finally:
            with self.lock:
                self.active -= 1


def _settings(**overrides):
    base = {
        "retrieval_k": 5,
        "confidence_threshold": 0.3,
        "llm_max_attempts": 1,
        "llm_concurrency": 2,
    }
    base.update(overrides)
    return Settings(**base, _env_file=None)


def _meta(**overrides):
    base = {
        "contract_type": "locacion",
        "contract_type_source": "x",
        "signing_date": date(2026, 3, 15),
        "signing_date_source": "detected",
        "warnings": [],
    }
    base.update(overrides)
    return ContractMeta(**base)


def test_review_builds_report_with_regime_clauses_and_gaps():
    split = split_contract(TEXT)
    retriever = FakeRetriever()
    report = run_review(
        split=split,
        meta=_meta(),
        retriever=retriever,
        llm=FakeLLM(),
        kb=FakeKb(),
        settings=_settings(),
        full_text=TEXT,
    )
    assert report.regime.regime == "DNU 70/2023"
    assert [c.clause_id for c in report.clauses] == ["c-01", "c-02"]
    assert all(q.regime == "DNU 70/2023" for q in retriever.queries)
    assert all(q.signing_date_i == 20260315 for q in retriever.queries)
    assert report.contract_gaps == []  # «precio» is in the clause text
    assert report.summary["risks"] == 2


def test_missing_signing_date_is_asked_for_before_any_work():
    with pytest.raises(SigningDateRequired):
        run_review(
            split=split_contract(TEXT),
            meta=_meta(signing_date=None),
            retriever=FakeRetriever(),
            llm=FakeLLM(),
            kb=FakeKb(),
            settings=_settings(),
            full_text=TEXT,
        )


def test_undetected_contract_type_is_an_error():
    with pytest.raises(ContractTypeUndetected):
        run_review(
            split=split_contract(TEXT),
            meta=_meta(contract_type=None),
            retriever=FakeRetriever(),
            llm=FakeLLM(),
            kb=FakeKb(),
            settings=_settings(),
            full_text=TEXT,
        )


def test_one_failing_clause_fails_the_whole_review_without_partial_report():
    with pytest.raises(LLMUnavailable):
        run_review(
            split=split_contract(TEXT),
            meta=_meta(),
            retriever=FakeRetriever(),
            llm=FakeLLM(fail=True),
            kb=FakeKb(),
            settings=_settings(),
            full_text=TEXT,
        )


def test_clauses_run_in_parallel_up_to_concurrency_limit():
    text = (
        TEXT
        + "\nCLÁUSULA TERCERA — DESTINO\nVivienda permanente.\n\nCLÁUSULA CUARTA — OTRA\nTexto.\n"
    )
    llm = FakeLLM(delay=0.05)
    run_review(
        split=split_contract(text),
        meta=_meta(),
        retriever=FakeRetriever(),
        llm=llm,
        kb=FakeKb(),
        settings=_settings(llm_concurrency=2),
        full_text=text,
    )
    assert llm.max_active == 2
