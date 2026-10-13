import re

import pytest

from src.review.gaps import find_gaps

ELEMENTS = [
    {
        "id": "Ley 27.551-1197",
        "element": "precio",
        "level": "high",
        "patterns": ["precio", "canon"],
    },
    {
        "id": "Ley 27.551-1200",
        "element": "domicilio de las partes",
        "level": "medium",
        "patterns": ["domicilio"],
    },
]


def test_present_element_produces_no_gap():
    text = "CLÁUSULA TERCERA — PRECIO\nEl precio mensual es de $200.000.\nDomicilio: calle 1."
    assert find_gaps(text, ELEMENTS) == []


def test_missing_element_is_a_heuristic_gap_for_manual_review():
    text = "CLÁUSULA PRIMERA — OBJETO\nEl locador da en locación el inmueble.\nDomicilio: calle 1."
    gaps = find_gaps(text, ELEMENTS)
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.type == "gap"
    assert gap.source == "heuristic"
    assert gap.needs_manual_review is True
    assert gap.article_refs == ["Ley 27.551-1197"]
    assert gap.searched_patterns == ["precio", "canon"]
    assert gap.level == "high"


def test_matching_ignores_case_and_accents():
    text = "EL PRÉCIO es pagadero mensualmente."
    assert find_gaps(text, ELEMENTS[:1]) == []


def test_preamble_text_counts_as_evidence():
    text = "Precio y domicilio pactados en el encabezado.\nCLÁUSULA PRIMERA — OBJETO\nTexto."
    assert find_gaps(text, ELEMENTS) == []


def test_gap_check_makes_no_external_calls(monkeypatch):
    import socket

    def _forbidden(*args, **kwargs):
        raise AssertionError("network call during the gap check")

    monkeypatch.setattr(socket, "socket", _forbidden)
    find_gaps("Texto.", ELEMENTS)


@pytest.mark.parametrize("bad", [["("], ["["]])
def test_invalid_pattern_is_reported_not_silently_skipped(bad):
    with pytest.raises(re.error):
        find_gaps(
            "Texto.", [{"id": "x-1", "element": "e", "level": "low", "patterns": bad}]
        )
