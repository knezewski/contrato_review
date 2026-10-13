"""CABA taxes — impuesto de sellos (spec §3, AC6, UC5; data-model.md §5).

Rate and threshold parameters come from KB records (the `params` field, see data/laws/caba/), not from code
(constitution I). For locación no amount is computed: the rate is pending until Ley Tarifaria 2026 is confirmed.

Failure modes (constitution IV):
- Price and currency are extracted from the text with regular expressions; if they cannot be found, no amount is computed.
- Currency USD: the KB threshold is in ARS, so comparison is impossible → no amount, a warning.
- No valuación fiscal → the base is unknown → no amount, a warning.
- The «vivienda única» flag is searched for by key phrases; if not found, the exemption is not asserted.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal

from src.report.model import StampTaxResult

AMOUNT = r"\$\s?([0-9]{1,3}(?:\.[0-9]{3})+|[0-9]+)"
PRICE_RE = re.compile(r"precio[^\n$]{0,120}?" + AMOUNT, re.IGNORECASE)
VALUATION_RE = re.compile(r"valuaci[oó]n fiscal[^\n$]{0,120}?" + AMOUNT, re.IGNORECASE)
USD_PRICE_RE = re.compile(
    r"(?:USD|U\$S|dólares)[^\n]{0,40}?([0-9]{1,3}(?:\.[0-9]{3})+|[0-9]+)", re.IGNORECASE
)
HOME_RE = re.compile(r"vivienda [uú]nica", re.IGNORECASE)


@dataclass
class ContractFacts:
    price_ars: Decimal | None
    valuation_ars: Decimal | None
    vivienda_unica: bool | None
    currency: str
    warnings: list[str] = field(default_factory=list)


def _amount(raw: str) -> Decimal:
    return Decimal(raw.replace(".", ""))


def _fold(text: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )


def extract_facts(text_es: str) -> ContractFacts:
    warnings: list[str] = []
    currency = "ARS"
    price = None
    usd = USD_PRICE_RE.search(text_es)
    if usd and not PRICE_RE.search(text_es):
        currency = "USD"
    match = PRICE_RE.search(text_es)
    if match:
        price = _amount(match.group(1))
    valuation = None
    match = VALUATION_RE.search(text_es)
    if match:
        valuation = _amount(match.group(1))
    home = True if HOME_RE.search(_fold(text_es)) else None
    return ContractFacts(
        price_ars=price,
        valuation_ars=valuation,
        vivienda_unica=home,
        currency=currency,
        warnings=warnings,
    )


def _params(records: list[dict], article: str) -> dict | None:
    for record in records:
        if record["article"] == article:
            return record.get("params")
    return None


def compute_stamp_tax(
    contract_type: str, facts: ContractFacts, records: list[dict]
) -> StampTaxResult:
    warnings = list(facts.warnings)

    if contract_type == "locacion":
        return StampTaxResult(
            contract_type="locacion",
            applies=True,
            payer="unknown",
            vivienda_unica_exemption=None,
            amount_ars=None,
            rate_status="pending",
            article_refs=[
                r["id"] for r in records if r["article"] == "sellos-locacion"
            ],
            no_norm_found=not any(r["article"] == "sellos-locacion" for r in records),
            warnings=warnings
            + ["alícuota de sellos para locación pendiente de la Ley Tarifaria 2026"],
        )

    home = facts.vivienda_unica
    article = (
        "sellos-compraventa-vivienda-unica"
        if home
        else "sellos-compraventa-no-vivienda-unica"
    )
    params = _params(records, article)
    refs = [r["id"] for r in records if r["article"] == article]
    if params is None:
        return StampTaxResult(
            contract_type="compraventa",
            applies=None,
            payer="unknown",
            vivienda_unica_exemption=home,
            amount_ars=None,
            rate_status="pending",
            article_refs=[],
            no_norm_found=True,
            warnings=warnings + ["CABA tax norm not found in the knowledge base"],
        )

    if home is None:
        warnings.append(
            "it is not determined whether the property is vivienda única; the exemption is not asserted"
        )
    if facts.currency == "USD":
        warnings.append(
            "price in USD, threshold in ARS: comparison is impossible without an exchange rate"
        )
    if facts.valuation_ars is None:
        warnings.append(
            "no valuación fiscal found in the text: the tax base is unknown"
        )
    if facts.price_ars is None:
        warnings.append("price not found in the text")

    base_known = (
        facts.price_ars is not None
        and facts.valuation_ars is not None
        and facts.currency == "ARS"
    )
    if not base_known or home is None:
        return StampTaxResult(
            contract_type="compraventa",
            applies=True,
            payer="shared",
            vivienda_unica_exemption=home,
            amount_ars=None,
            rate_status="confirmed",
            article_refs=refs,
            no_norm_found=False,
            warnings=warnings,
        )

    base = max(facts.price_ars, facts.valuation_ars)
    split_payer = "shared"
    if home:
        threshold = Decimal(str(params["threshold_ars"]))
        if base <= threshold:
            amount = Decimal(0)
            exempt = True
        else:
            amount = (base - threshold) * Decimal(str(params["rate_excess"]))
            exempt = False
    else:
        amount = base * Decimal(str(params["rate"]))
        exempt = None

    return StampTaxResult(
        contract_type="compraventa",
        applies=True,
        payer=split_payer,
        vivienda_unica_exemption=exempt,
        amount_ars=amount,
        rate_status="confirmed",
        article_refs=refs,
        no_norm_found=False,
        warnings=warnings,
    )
