"""Shared fixtures for contract tests: a real norm index (in a temporary directory) and fake models."""

from pathlib import Path

import chromadb
import pytest

from src.api.deps import Deps, load_glossary
from src.config import Settings
from src.kb.embedder import E5Embedder
from src.kb.index import build
from src.kb.queries import KbQueries
from src.retrieval.retrieve import Retriever
from src.review.errors import LLMProviderError
from src.store.reports import ReportStore

LAWS = Path(__file__).resolve().parents[2] / "data" / "laws"


@pytest.fixture(scope="module")
def real_index(tmp_path_factory):
    path = tmp_path_factory.mktemp("chroma_contract")
    client = chromadb.PersistentClient(path=str(path))
    embedder = E5Embedder()
    build(client, embedder, LAWS, "ar_law", reset=True)
    return client.get_collection("ar_law"), embedder


class EchoLLM:
    """Always references the first norm found (allowed by constitution I)."""

    def __init__(self):
        self.calls = 0

    def translate(self, items, lang):
        return dict(items)

    def review_clause(self, clause_text, norms, contract_type):
        self.calls += 1
        return {
            "findings": [
                {
                    "type": "risk",
                    "level": "low",
                    "explanation_es": "Revisar frente a la norma citada.",
                    "article_refs": [norms[0].id],
                    "no_norm_found": False,
                }
            ]
        }


class FailingLLM:
    def review_clause(self, clause_text, norms, contract_type):
        raise LLMProviderError("servicio no disponible (prueba)")


@pytest.fixture
def make_deps(real_index, tmp_path):
    coll, embedder = real_index

    def _make(llm=None, **settings):
        settings.setdefault("confidence_threshold", 0.3)
        config = Settings(_env_file=None, **settings)
        return Deps(
            settings=config,
            retriever=Retriever(coll, embedder),
            kb=KbQueries(coll),
            llm=llm or EchoLLM(),
            report_store=ReportStore(
                str(tmp_path / "reports.db"),
                retention_days=config.report_retention_days,
            ),
            glossary=load_glossary(),
        )

    return _make
