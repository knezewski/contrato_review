from datetime import date

import pytest

from src.ingest.errors import SigningDateRequired
from src.review.regime import select_regime

RECORDS = [
    {
        "jurisdiction": "nacional",
        "contract_type": "locacion",
        "regime": "Ley 27.551",
        "valid_from_i": 20200701,
        "valid_to_i": 20231229,
    },
    {
        "jurisdiction": "nacional",
        "contract_type": "locacion",
        "regime": "DNU 70/2023",
        "valid_from_i": 20231230,
        "valid_to_i": 99991231,
    },
    {
        "jurisdiction": "nacional",
        "contract_type": "compraventa",
        "regime": "DNU 70/2023",
        "valid_from_i": 20231230,
        "valid_to_i": 99991231,
    },
    {
        "jurisdiction": "CABA",
        "contract_type": "locacion",
        "regime": "Ley Tarifaria CABA 2026",
        "valid_from_i": 20260101,
        "valid_to_i": 99991231,
    },
]


@pytest.mark.parametrize(
    ("signing", "expected"),
    [
        (date(2026, 3, 15), "DNU 70/2023"),
        (date(2022, 10, 10), "Ley 27.551"),
        (date(2023, 12, 29), "Ley 27.551"),
        (date(2023, 12, 30), "DNU 70/2023"),
    ],
)
def test_lease_regime_follows_signing_date(signing, expected):
    choice = select_regime(signing, "locacion", RECORDS)
    assert choice.regime == expected


def test_sale_uses_the_same_date_rule():
    choice = select_regime(date(2026, 3, 15), "compraventa", RECORDS)
    assert choice.regime == "DNU 70/2023"


def test_caba_records_do_not_decide_the_national_regime():
    choice = select_regime(date(2026, 3, 15), "locacion", RECORDS)
    assert choice.regime == "DNU 70/2023"
    assert "Ley Tarifaria CABA 2026" not in choice.candidates


def test_missing_signing_date_raises():
    with pytest.raises(SigningDateRequired):
        select_regime(None, "locacion", RECORDS)


def test_no_regime_for_date_returns_none_regime():
    choice = select_regime(date(2019, 1, 1), "locacion", RECORDS)
    assert choice.regime is None


def test_two_regimes_for_one_date_is_a_data_error():
    records = RECORDS + [
        {
            "jurisdiction": "nacional",
            "contract_type": "locacion",
            "regime": "Otro",
            "valid_from_i": 20230101,
            "valid_to_i": 99991231,
        },
    ]
    with pytest.raises(ValueError, match="several regimes"):
        select_regime(date(2026, 3, 15), "locacion", records)
