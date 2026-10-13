from datetime import date

from src.ingest.meta import detect_meta

LEASE = "CONTRATO DE LOCACIÓN DE VIVIENDA\n\nEn CABA, a los 15 días del mes de marzo de 2026.\n"
SALE = "BOLETO DE COMPRAVENTA DE INMUEBLE\n\nEn CABA, a los 20 días del mes de junio de 2025.\n"


def test_lease_type_and_signing_date_detected():
    meta = detect_meta(LEASE)
    assert meta.contract_type == "locacion"
    assert meta.signing_date == date(2026, 3, 15)
    assert meta.signing_date_source == "detected"


def test_sale_type_detected():
    meta = detect_meta(SALE)
    assert meta.contract_type == "compraventa"
    assert meta.signing_date == date(2025, 6, 20)


def test_missing_date_returns_none():
    meta = detect_meta("CONTRATO DE LOCACIÓN\n\nLas partes firman el presente.\n")
    assert meta.contract_type == "locacion"
    assert meta.signing_date is None


def test_conflicting_dates_are_ambiguous():
    text = LEASE + "\nEn CABA, a los 2 días del mes de abril de 2026.\n"
    meta = detect_meta(text)
    assert meta.signing_date is None
    assert any("ambiguous" in w for w in meta.warnings)


def test_user_supplied_date_wins_and_conflict_is_noted():
    meta = detect_meta(LEASE, user_signing_date=date(2022, 10, 10))
    assert meta.signing_date == date(2022, 10, 10)
    assert meta.signing_date_source == "user_provided"
    assert any("2026-03-15" in w for w in meta.warnings)


def test_unknown_type_returns_none():
    meta = detect_meta("Texto sin tipo de contrato. Se paga mensualmente.")
    assert meta.contract_type is None
