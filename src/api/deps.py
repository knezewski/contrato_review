"""Service dependencies: settings, search, KB, model, report store, glossary.

In tests everything is replaced via create_app(deps=...).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.config import Settings
from src.review.errors import LLMProviderError

GLOSSARY_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "glossary" / "es_terms.json"
)


def load_glossary(path: Path = GLOSSARY_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class Deps:
    settings: Settings
    retriever: object
    kb: object
    llm: object
    report_store: object
    translator: object | None = None
    glossary: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if self.translator is None:
            self.translator = self.llm


class _NoKeyLLM:
    """A stand-in client used when ANTHROPIC_API_KEY is not set: a provider failure rather than a service crash."""

    def review_clause(self, clause_text, norms, contract_type):
        raise LLMProviderError("ANTHROPIC_API_KEY is not set")

    def translate(self, items, lang):
        raise LLMProviderError("ANTHROPIC_API_KEY is not set")


def build_default_deps(settings: Settings) -> Deps:
    import chromadb

    from src.kb.embedder import E5Embedder
    from src.kb.queries import KbQueries
    from src.retrieval.retrieve import Retriever
    from src.store.reports import ReportStore

    client = chromadb.PersistentClient(path=settings.chroma_path)
    collection = client.get_or_create_collection(
        settings.chroma_collection, metadata={"hnsw:space": "cosine"}
    )
    embedder = E5Embedder(settings.embed_model)

    if settings.anthropic_api_key is None:
        llm = _NoKeyLLM()
    else:
        from src.review.llm.anthropic_client import AnthropicClaudeClient

        llm = AnthropicClaudeClient(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.llm_model,
            timeout_s=settings.llm_timeout_s,
            max_attempts=settings.llm_max_attempts,
        )
    store = ReportStore(settings.reports_db_path, settings.report_retention_days)
    return Deps(
        settings=settings,
        retriever=Retriever(collection, embedder),
        kb=KbQueries(collection),
        llm=llm,
        report_store=store,
        glossary=load_glossary(),
    )
