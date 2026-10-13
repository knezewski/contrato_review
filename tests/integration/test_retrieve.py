"""Retrieval on the real index (real embedding model, real JSON from data/laws).

The index is built in a temporary directory, so the test does not depend on the state of data/chroma.
Requires a locally cached intfloat/multilingual-e5-large model (HF_HUB_OFFLINE=1 is allowed).
"""

from pathlib import Path

import chromadb
import pytest

from src.kb.embedder import E5Embedder
from src.kb.index import COLLECTION_METADATA, build
from src.retrieval.retrieve import RetrievalQuery, Retriever

LAWS = Path(__file__).resolve().parents[2] / "data" / "laws"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def retriever(tmp_path_factory):
    path = tmp_path_factory.mktemp("chroma")
    client = chromadb.PersistentClient(path=str(path))
    embedder = E5Embedder()
    build(client, embedder, LAWS, "ar_law", reset=True)
    collection = client.get_collection("ar_law", embedding_function=None)
    assert (
        collection.metadata["hnsw:space"]
        == COLLECTION_METADATA["hnsw:space"]
        == "cosine"
    )
    return Retriever(collection, embedder)


PLAZO = "El plazo de la locación es de dos (2) años desde el 1 de abril de 2026."


def test_signing_before_2024_selects_ley_27551(retriever):
    norms = retriever.search(
        RetrievalQuery(
            text=PLAZO,
            signing_date_i=20231229,
            contract_type="locacion",
            regime="Ley 27.551",
            k=5,
        )
    )
    national = [n for n in norms if n.jurisdiction == "nacional"]
    assert national, "no national norms"
    assert {n.regime for n in national} == {"Ley 27.551"}


def test_signing_on_30_dec_2023_selects_dnu(retriever):
    norms = retriever.search(
        RetrievalQuery(
            text=PLAZO,
            signing_date_i=20231230,
            contract_type="locacion",
            regime="DNU 70/2023",
            k=5,
        )
    )
    national = [n for n in norms if n.jurisdiction == "nacional"]
    assert national
    assert {n.regime for n in national} == {"DNU 70/2023"}


def test_only_nacional_and_caba_are_returned(retriever):
    norms = retriever.search(
        RetrievalQuery(
            text=PLAZO,
            signing_date_i=20260315,
            contract_type="locacion",
            regime="DNU 70/2023",
            k=10,
        )
    )
    assert norms
    assert {n.jurisdiction for n in norms} <= {"nacional", "CABA"}


def test_caba_stamp_tax_is_retrieved_for_lease_in_2026(retriever):
    norms = retriever.search(
        RetrievalQuery(
            text="Impuesto de sellos sobre el contrato de locación de vivienda",
            signing_date_i=20260315,
            contract_type="locacion",
            regime="DNU 70/2023",
            k=5,
        )
    )
    assert any(
        n.jurisdiction == "CABA" and n.article == "sellos-locacion" for n in norms
    )


def test_scores_are_similarities_in_range(retriever):
    norms = retriever.search(
        RetrievalQuery(
            text=PLAZO,
            signing_date_i=20231230,
            contract_type="locacion",
            regime="DNU 70/2023",
            k=3,
        )
    )
    assert norms
    assert all(-1.0 <= n.score <= 1.0 for n in norms)
    assert norms == sorted(norms, key=lambda n: n.score, reverse=True)
