"""Selecting the legal regime for the whole contract by signing date (spec §3, AC4; research.md R5).

The regime is taken from KB records with jurisdiction=nacional, the contract's contract_type and a period
that contains the signing date. Regimes are not hard-coded.

Failure modes:
- no date → SigningDateRequired (ask the user, AC13);
- no national regime for the date → regime=None (the report says no norm was found);
- two different regimes for the date → ValueError: a data error in the KB, not a choice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.ingest.errors import SigningDateRequired


@dataclass(frozen=True)
class RegimeChoice:
    regime: str | None
    valid_from_i: int | None
    valid_to_i: int | None
    candidates: tuple[str, ...]


def select_regime(
    signing_date: date | None, contract_type: str, national_records: list[dict]
) -> RegimeChoice:
    if signing_date is None:
        raise SigningDateRequired("signing date not provided")
    day = signing_date.year * 10000 + signing_date.month * 100 + signing_date.day

    matching = [
        r
        for r in national_records
        if r["jurisdiction"] == "nacional"
        and r["contract_type"] == contract_type
        and r["valid_from_i"] <= day <= r["valid_to_i"]
    ]
    regimes = sorted({r["regime"] for r in matching})
    if not regimes:
        return RegimeChoice(
            regime=None, valid_from_i=None, valid_to_i=None, candidates=()
        )
    if len(regimes) > 1:
        raise ValueError(f"several regimes in the KB for date {day}: {regimes}")

    chosen = regimes[0]
    period = next(r for r in matching if r["regime"] == chosen)
    return RegimeChoice(
        regime=chosen,
        valid_from_i=period["valid_from_i"],
        valid_to_i=period["valid_to_i"],
        candidates=tuple(regimes),
    )
