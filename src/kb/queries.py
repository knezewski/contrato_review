"""Reads the KB from Chroma for the analysis stage: regimes, required elements, taxes (T5).

Period filters use int YYYYMMDD only (constitution II). Lists and dicts are stored in metadata
as JSON strings (Chroma does not accept lists in metadata).
"""

from __future__ import annotations

import json


class KbQueries:
    def __init__(self, collection):
        self._collection = collection

    def count(self) -> int:
        return self._collection.count()

    def national_regime_records(self, contract_type: str) -> list[dict]:
        result = self._collection.get(
            where={
                "$and": [{"jurisdiction": "nacional"}, {"contract_type": contract_type}]
            },
            include=["metadatas"],
        )
        return list(result["metadatas"])

    def _active(self, kind: str, contract_type: str, signing_date_i: int) -> list[dict]:
        result = self._collection.get(
            where={
                "$and": [
                    {"kind": kind},
                    {"contract_type": {"$in": [contract_type, "all"]}},
                    {"valid_from_i": {"$lte": signing_date_i}},
                    {"valid_to_i": {"$gte": signing_date_i}},
                ]
            },
            include=["metadatas"],
        )
        rows = []
        for norm_id, meta in zip(result["ids"], result["metadatas"]):
            row = dict(meta)
            row["id"] = norm_id
            rows.append(row)
        return rows

    def required_elements(self, contract_type: str, signing_date_i: int) -> list[dict]:
        rows = self._active("required_element", contract_type, signing_date_i)
        return [
            {
                "id": row["id"],
                "element": row["element"],
                "level": row["level"],
                "patterns": json.loads(row["patterns_json"]),
            }
            for row in rows
        ]

    def tax_records(self, contract_type: str, signing_date_i: int) -> list[dict]:
        rows = self._active("tax", contract_type, signing_date_i)
        return [
            {
                "id": row["id"],
                "article": row["article"],
                "contract_type": row["contract_type"],
                "params": json.loads(row["params_json"])
                if row.get("params_json")
                else None,
            }
            for row in rows
        ]
