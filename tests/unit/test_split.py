import pytest

from src.ingest.errors import NoClausesDetected
from src.ingest.split import split_contract

TEXT = """CONTRATO DE LOCACIÓN DE VIVIENDA

En la Ciudad Autónoma de Buenos Aires, a los 15 días del mes de marzo de 2026.

CLÁUSULA PRIMERA — OBJETO
El locador da en locación el inmueble.

CLÁUSULA SEGUNDA — PRECIO
El precio mensual es de pesos doscientos mil.

CLÁUSULA TERCERA
"""


def test_preamble_is_separate_block():
    result = split_contract(TEXT)
    assert "CONTRATO DE LOCACIÓN DE VIVIENDA" in result.preamble
    assert "CLÁUSULA PRIMERA" not in result.preamble


def test_clauses_get_sequential_ids_markers_and_headings():
    result = split_contract(TEXT)
    assert [c.clause_id for c in result.clauses] == ["c-01", "c-02"]
    first, second = result.clauses
    assert first.marker == "CLÁUSULA PRIMERA"
    assert first.heading == "OBJETO"
    assert second.heading == "PRECIO"
    assert "pesos doscientos mil" in second.text_es


def test_empty_clause_is_dropped_with_warning():
    result = split_contract(TEXT)
    assert len(result.clauses) == 2
    assert any("CLÁUSULA TERCERA" in w for w in result.warnings)


def test_articulo_markers_are_recognized():
    text = "ARTÍCULO 1 — Objeto\nTexto del artículo uno.\n\nARTÍCULO 2 — Plazo\nTexto del artículo dos.\n"
    result = split_contract(text)
    assert [c.marker for c in result.clauses] == ["ARTÍCULO 1", "ARTÍCULO 2"]


def test_numbering_is_used_only_without_legal_markers():
    numbered = "1. Objeto\nTexto uno.\n2. Precio\nTexto dos.\n"
    result = split_contract(numbered)
    assert [c.marker for c in result.clauses] == ["1.", "2."]

    mixed = (
        "CLÁUSULA PRIMERA — X\nDetalle:\n1. sub-punto dentro de la cláusula\nTexto.\n"
    )
    result = split_contract(mixed)
    assert [c.marker for c in result.clauses] == ["CLÁUSULA PRIMERA"]


def test_no_markers_raises():
    with pytest.raises(NoClausesDetected):
        split_contract("Texto libre sin marcadores de cláusula.")
