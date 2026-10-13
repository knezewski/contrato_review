import json
import re
from pathlib import Path

import pytest

LAWS = Path(__file__).resolve().parents[2] / "data" / "laws"


def _records():
    for path in sorted(LAWS.rglob("*.json")):
        for record in json.loads(path.read_text(encoding="utf-8")):
            yield path, record


def test_every_record_has_source_and_validity():
    for path, record in _records():
        for field in (
            "article",
            "regime",
            "jurisdiction",
            "contract_type",
            "valid_from",
            "source_url",
            "text",
        ):
            assert field in record, (
                f"{path.name}: {record.get('article')} is missing field {field}"
            )
        assert record["source_url"].startswith("https://"), path.name


def test_unverified_records_are_marked_for_source_check():
    for path, record in _records():
        if record.get("verbatim") is False:
            assert record.get("note"), (
                f"{path.name}: {record['article']} verbatim=false without note"
            )


def test_required_element_records_have_compilable_patterns():
    for path, record in _records():
        if record.get("kind") != "required_element":
            continue
        assert record.get("element"), path.name
        assert record.get("level") in {"low", "medium", "high"}, path.name
        patterns = record.get("patterns")
        assert isinstance(patterns, list) and patterns, path.name
        for pattern in patterns:
            re.compile(pattern, re.IGNORECASE)


def test_caba_records_are_only_in_caba_folder():
    for path, record in _records():
        if record["jurisdiction"] == "CABA":
            assert "caba" in path.parts, (
                f"{path.name}: CABA record outside data/laws/caba"
            )


def test_no_duplicate_ids_in_kb():
    ids = [f"{r['regime']}-{r['article']}" for _, r in _records()]
    assert len(ids) == len(set(ids))


@pytest.mark.xfail(
    strict=True,
    reason="CCyC norms for compraventa (arts. 1123–1171) and the DNU 70/2023 / Ley 27.551 regimes for sales "
    "are not in the KB: they need checking against the primary source (constitution I). Remove the xfail once added.",
)
def test_sale_and_lease_both_have_national_regimes():
    national = [r for _, r in _records() if r["jurisdiction"] == "nacional"]
    for contract_type in ("compraventa", "locacion"):
        regimes = {r["regime"] for r in national if r["contract_type"] == contract_type}
        assert {"Ley 27.551", "DNU 70/2023"} <= regimes, contract_type
