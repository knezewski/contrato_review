"""Norm index: JSON from data/laws → Chroma collection `ar_law` (data-model.md §3).

Failure modes (constitution IV):
- A record without a required field → KbRecordError (the index is not built partially).
- An unparseable date → DateParseError from kb/dates.py (the index is not built).
- A duplicate ID `{regime}-{article}` → KbRecordError: a data error, not an overwrite.
- Changing the embedding model or the ID scheme requires a full re-index (`--reset`).

CLI:
    python -m src.kb.index build --laws data/laws [--reset]
    python -m src.kb.index check
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import Settings
from src.kb.dates import to_yyyymmdd

COLLECTION_METADATA = {"hnsw:space": "cosine"}
REQUIRED_FIELDS = (
    "article",
    "title",
    "regime",
    "jurisdiction",
    "contract_type",
    "valid_from",
    "source_url",
    "text",
)
CHECK_QUERY = "plazo mínimo locación"


class KbRecordError(ValueError):
    pass


def record_id(record: dict) -> str:
    return f"{record['regime']}-{record['article']}"


def normalize_record(record: dict) -> dict:
    """Returns {id, document, metadata} for Chroma. Metadata values are str/int/float/bool only."""
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        raise KbRecordError(
            f"record {record.get('article')!r} is missing fields: {', '.join(missing)}"
        )

    valid_from_i = to_yyyymmdd(record["valid_from"], open_end=False)
    valid_to_i = to_yyyymmdd(record.get("valid_to"), open_end=True)
    if valid_to_i < valid_from_i:
        raise KbRecordError(
            f"valid_to is earlier than valid_from in record {record_id(record)}"
        )

    metadata = {
        "jurisdiction": record["jurisdiction"],
        "contract_type": record["contract_type"],
        "regime": record["regime"],
        "article": str(record["article"]),
        "title": record["title"],
        "valid_from_i": valid_from_i,
        "valid_to_i": valid_to_i,
        "source_url": record["source_url"],
        "verbatim": bool(record.get("verbatim", False)),
        "kind": record.get("kind", "norm"),
    }
    if metadata["kind"] == "required_element":
        patterns = record.get("patterns")
        if not patterns:
            raise KbRecordError(
                f"required_element without patterns: {record_id(record)}"
            )
        metadata["element"] = record["element"]
        metadata["level"] = record["level"]
        metadata["patterns_json"] = json.dumps(patterns, ensure_ascii=False)
    if metadata["kind"] == "tax" and record.get("params") is not None:
        metadata["params_json"] = json.dumps(record["params"], ensure_ascii=False)

    return {"id": record_id(record), "document": record["text"], "metadata": metadata}


def load_records(laws_dir: Path) -> list[dict]:
    """All JSON files in the directory, recursively; each file is a list of records."""
    records: list[dict] = []
    for path in sorted(laws_dir.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise KbRecordError(f"{path}: a list of records is expected")
        records.extend(data)
    return records


def build(
    client, embedder, laws_dir: Path, collection_name: str, reset: bool = False
) -> int:
    if reset:
        existing = {
            c if isinstance(c, str) else c.name for c in client.list_collections()
        }
        if collection_name in existing:
            client.delete_collection(collection_name)
    collection = client.get_or_create_collection(
        collection_name, metadata=COLLECTION_METADATA
    )

    normalized = [normalize_record(record) for record in load_records(laws_dir)]
    ids = [item["id"] for item in normalized]
    duplicates = {item for item in ids if ids.count(item) > 1}
    if duplicates:
        raise KbRecordError(f"duplicate IDs: {sorted(duplicates)}")
    if not normalized:
        return 0

    embeddings = embedder.embed_passages([item["document"] for item in normalized])
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=[item["document"] for item in normalized],
        metadatas=[item["metadata"] for item in normalized],
    )
    return len(normalized)


def _main() -> None:
    import chromadb

    from src.kb.embedder import E5Embedder

    settings = Settings()
    parser = argparse.ArgumentParser(prog="python -m src.kb.index")
    sub = parser.add_subparsers(dest="command", required=True)
    build_cmd = sub.add_parser("build")
    build_cmd.add_argument("--laws", default="data/laws")
    build_cmd.add_argument("--reset", action="store_true")
    sub.add_parser("check")
    args = parser.parse_args()

    client = chromadb.PersistentClient(path=settings.chroma_path)
    embedder = E5Embedder(settings.embed_model)

    if args.command == "build":
        count = build(
            client,
            embedder,
            Path(args.laws),
            settings.chroma_collection,
            reset=args.reset,
        )
        print(f"indexed: {count}")
    else:
        collection = client.get_collection(settings.chroma_collection)
        print(f"records: {collection.count()}")
        result = collection.query(
            query_embeddings=[embedder.embed_query(CHECK_QUERY)],
            n_results=min(5, collection.count()),
            include=["metadatas", "distances"],
        )
        for meta, distance in zip(result["metadatas"][0], result["distances"][0]):
            print(f"{meta['regime']} art.{meta['article']} score={1 - distance:.3f}")


if __name__ == "__main__":
    _main()
