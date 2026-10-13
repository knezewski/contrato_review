import json
from pathlib import Path

import chromadb
import pytest

from src.kb.dates import DateParseError
from src.kb.index import COLLECTION_METADATA, KbRecordError, build, normalize_record


class FakeEmbedder:
    def embed_passages(self, texts):
        return [[float(len(t)), 1.0, 0.0] for t in texts]


def _record(**overrides):
    base = {
        "article": "1198",
        "title": "Plazo mínimo",
        "jurisdiction": "nacional",
        "contract_type": "locacion",
        "regime": "DNU 70/2023",
        "valid_from": "2023-12-30",
        "valid_to": None,
        "source_url": "https://example.test/norma",
        "verbatim": False,
        "text": "Texto de prueba.",
    }
    base.update(overrides)
    return base


def _write_laws(directory: Path, records: list[dict]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "laws.json").write_text(
        json.dumps(records, ensure_ascii=False), encoding="utf-8"
    )
    return directory


@pytest.fixture
def client():
    return chromadb.EphemeralClient()


def test_collection_uses_cosine_space(client, tmp_path):
    laws = _write_laws(tmp_path / "laws", [_record()])
    build(client, FakeEmbedder(), laws, "ar_law_test_cosine")
    collection = client.get_collection("ar_law_test_cosine")
    assert (
        collection.metadata["hnsw:space"]
        == COLLECTION_METADATA["hnsw:space"]
        == "cosine"
    )


def test_id_scheme_and_int_dates(client, tmp_path):
    laws = _write_laws(tmp_path / "laws", [_record()])
    build(client, FakeEmbedder(), laws, "ar_law_test_ids")
    got = client.get_collection("ar_law_test_ids").get(
        ids=["DNU 70/2023-1198"], include=["metadatas"]
    )
    meta = got["metadatas"][0]
    assert meta["valid_from_i"] == 20231230
    assert meta["valid_to_i"] == 99991231
    assert meta["kind"] == "norm"
    assert isinstance(meta["valid_from_i"], int)


def test_null_valid_to_is_sentinel_and_bad_date_fails():
    assert normalize_record(_record())["metadata"]["valid_to_i"] == 99991231
    with pytest.raises(DateParseError):
        normalize_record(_record(valid_from="2023-13-01"))
    with pytest.raises(DateParseError):
        normalize_record(_record(valid_to=""))


def test_duplicate_ids_are_rejected(client, tmp_path):
    laws = _write_laws(tmp_path / "laws", [_record(), _record(title="Otra copia")])
    with pytest.raises(KbRecordError, match="duplicate"):
        build(client, FakeEmbedder(), laws, "ar_law_test_dup")


def test_required_element_keeps_patterns_as_json(client, tmp_path):
    record = _record(
        kind="required_element",
        element="precio",
        level="high",
        patterns=["precio", "canon"],
        article="1197",
        regime="Ley 27.551",
        valid_from="2020-07-01",
        valid_to="2023-12-29",
    )
    normalized = normalize_record(record)["metadata"]
    assert json.loads(normalized["patterns_json"]) == ["precio", "canon"]
    assert normalized["element"] == "precio"
