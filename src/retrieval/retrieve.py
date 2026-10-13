"""Norm search per clause with filters (data-model.md §3, RetrievedNorm; research.md R2, R4, R5).

Filters are built in build_where and run in Chroma:
- jurisdiction ∈ {nacional, CABA};
- the contract's contract_type (or `all`);
- validity period: valid_from_i ≤ D ≤ valid_to_i, D = int YYYYMMDD;
- regime — only for national norms; CABA records have no regime and are filtered by period only.

score = 1 − distance (for cosine in Chroma, distance = 1 − similarity).
Chroma specifics (where dicts, distance) stay in this file (R2).
"""

from __future__ import annotations

from dataclasses import dataclass

ALLOWED_JURISDICTIONS = ("nacional", "CABA")


@dataclass(frozen=True)
class RetrievalQuery:
    text: str  # clause text in Spanish
    signing_date_i: int  # YYYYMMDD
    contract_type: str  # "compraventa" | "locacion"
    regime: str | None = None  # regime chosen for the whole contract (for nacional)
    k: int = 5


@dataclass(frozen=True)
class RetrievedNorm:
    id: str
    jurisdiction: str
    regime: str
    article: str
    title: str
    source_url: str
    verbatim: bool
    text: str
    kind: str
    score: float


def build_where(query: RetrievalQuery) -> dict:
    conditions: list[dict] = [
        {"jurisdiction": {"$in": list(ALLOWED_JURISDICTIONS)}},
        {"contract_type": {"$in": [query.contract_type, "all"]}},
        {"valid_from_i": {"$lte": query.signing_date_i}},
        {"valid_to_i": {"$gte": query.signing_date_i}},
    ]
    if query.regime is not None:
        conditions.append({"$or": [{"jurisdiction": "CABA"}, {"regime": query.regime}]})
    return {"$and": conditions}


class Retriever:
    def __init__(self, collection, embedder):
        self._collection = collection
        self._embedder = embedder

    def search(self, query: RetrievalQuery) -> list[RetrievedNorm]:
        if self._collection.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[self._embedder.embed_query(query.text)],
            n_results=min(query.k, self._collection.count()),
            where=build_where(query),
            include=["metadatas", "documents", "distances"],
        )
        norms: list[RetrievedNorm] = []
        for norm_id, meta, document, distance in zip(
            result["ids"][0],
            result["metadatas"][0],
            result["documents"][0],
            result["distances"][0],
        ):
            norms.append(
                RetrievedNorm(
                    id=norm_id,
                    jurisdiction=meta["jurisdiction"],
                    regime=meta["regime"],
                    article=meta["article"],
                    title=meta["title"],
                    source_url=meta["source_url"],
                    verbatim=bool(meta["verbatim"]),
                    text=document,
                    kind=meta.get("kind", "norm"),
                    score=1.0 - float(distance),
                )
            )
        return norms
