from decimal import Decimal

from src.review.stamp_tax import compute_stamp_tax, extract_facts

SALE_PARAMS = {
    "threshold_ars": 226100000,
    "rate_excess": 0.035,
    "split": {"buyer": 0.5, "seller": 0.5},
    "base": "max(price, valuacion_fiscal)",
}
NON_HOME_PARAMS = {
    "rate": 0.027,
    "split": {"buyer": 0.5, "seller": 0.5},
    "base": "max(price, valuacion_fiscal)",
}
RECORDS = [
    {
        "id": "vu",
        "contract_type": "compraventa",
        "article": "sellos-compraventa-vivienda-unica",
        "params": SALE_PARAMS,
    },
    {
        "id": "nvu",
        "contract_type": "compraventa",
        "article": "sellos-compraventa-no-vivienda-unica",
        "params": NON_HOME_PARAMS,
    },
    {
        "id": "loc",
        "contract_type": "locacion",
        "article": "sellos-locacion",
        "params": None,
    },
]


def _facts(price=None, valuation=None, home=True, currency="ARS"):
    from src.review.stamp_tax import ContractFacts

    return ContractFacts(
        price_ars=price,
        valuation_ars=valuation,
        vivienda_unica=home,
        currency=currency,
        warnings=[],
    )


def test_home_below_threshold_is_exempt_for_both_parties():
    result = compute_stamp_tax(
        "compraventa", _facts(Decimal(200000000), Decimal(150000000)), RECORDS
    )
    assert result.vivienda_unica_exemption is True
    assert result.amount_ars == Decimal(0)
    assert result.payer == "shared"


def test_home_above_threshold_pays_rate_on_excess_only():
    result = compute_stamp_tax(
        "compraventa", _facts(Decimal(300000000), Decimal(250000000)), RECORDS
    )
    assert result.vivienda_unica_exemption is False
    assert result.amount_ars == (Decimal(300000000) - Decimal(226100000)) * Decimal(
        "0.035"
    )


def test_base_is_the_higher_of_price_and_valuation():
    result = compute_stamp_tax(
        "compraventa", _facts(Decimal(200000000), Decimal(300000000)), RECORDS
    )
    assert result.amount_ars == (Decimal(300000000) - Decimal(226100000)) * Decimal(
        "0.035"
    )


def test_non_home_pays_flat_rate_on_base():
    result = compute_stamp_tax(
        "compraventa",
        _facts(Decimal(100000000), Decimal(90000000), home=False),
        RECORDS,
    )
    assert result.amount_ars == Decimal(100000000) * Decimal("0.027")


def test_missing_valuation_means_no_amount_and_a_warning():
    result = compute_stamp_tax("compraventa", _facts(Decimal(200000000), None), RECORDS)
    assert result.amount_ars is None
    assert any("valuación fiscal" in w for w in result.warnings)


def test_usd_price_cannot_be_compared_with_ars_threshold():
    result = compute_stamp_tax(
        "compraventa", _facts(Decimal(150000), Decimal(150000), currency="USD"), RECORDS
    )
    assert result.amount_ars is None
    assert any("USD" in w for w in result.warnings)


def test_lease_is_pending_with_no_amount_and_no_guessed_payer():
    result = compute_stamp_tax("locacion", _facts(), RECORDS)
    assert result.rate_status == "pending"
    assert result.amount_ars is None
    assert result.payer == "unknown"


def test_extract_facts_reads_price_and_valuation():
    text = (
        "El precio de la compraventa es de pesos doscientos mil ($200.000.000).\n"
        "La valuación fiscal del inmueble es de $150.000.000.\n"
        "El inmueble es vivienda única, familiar y de ocupación permanente.\n"
    )
    facts = extract_facts(text)
    assert facts.price_ars == Decimal(200000000)
    assert facts.valuation_ars == Decimal(150000000)
    assert facts.vivienda_unica is True


def test_extract_facts_without_valuation_keeps_none():
    facts = extract_facts("El precio es $100.000.")
    assert facts.valuation_ars is None
