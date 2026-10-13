import pytest

from src.report.i18n.disclaimer import DISCLAIMER
from src.report.render import render_report
from src.review.errors import LLMInvalidOutput

GLOSSARY = [
    {"es": "locación", "en": "lease", "ru": "аренда"},
    {"es": "impuesto de sellos", "en": "stamp tax", "ru": "гербовый сбор"},
]

REPORT = {
    "contract_type": "locacion",
    "signing_date": "2026-03-15",
    "regime": {
        "regime": "DNU 70/2023",
        "valid_from_i": 20231230,
        "valid_to_i": 99991231,
    },
    "summary": {"risks": 1, "gaps": 0, "mismatches": 0, "manual_review": 0},
    "warnings": [],
    "stamp_tax": None,
    "contract_gaps": [],
    "clauses": [
        {
            "clause_id": "c-01",
            "marker": "CLÁUSULA PRIMERA",
            "heading": "OBJETO",
            "needs_manual_review": False,
            "article_refs": ["DNU 70/2023-1198"],
            "findings": [
                {
                    "type": "risk",
                    "level": "low",
                    "explanation_es": "Contrato de locación con plazo mínimo.",
                    "article_refs": ["DNU 70/2023-1198"],
                    "no_norm_found": False,
                    "source": "llm",
                    "needs_manual_review": False,
                    "searched_patterns": [],
                }
            ],
        }
    ],
}


class FakeTranslator:
    def __init__(self, keep_terms=True):
        self.keep_terms = keep_terms
        self.seen = None

    def translate(self, items, lang):
        self.seen = dict(items)
        out = {}
        for key, text in items.items():
            if self.keep_terms:
                out[key] = text.replace("locación", "lease (locación)")
            else:
                out[key] = text.replace("locación", "lease")
        return out


def test_disclaimer_is_present_in_every_language():
    for lang in ("es", "en", "ru"):
        rendered = render_report(REPORT, lang, FakeTranslator(), GLOSSARY)
        assert rendered["disclaimer"] == DISCLAIMER[lang]
        assert rendered["disclaimer"]


def test_spanish_render_makes_no_translation_call():
    translator = FakeTranslator()
    rendered = render_report(REPORT, "es", translator, GLOSSARY)
    assert translator.seen is None
    assert (
        rendered["clauses"][0]["findings"][0]["explanation"]
        == REPORT["clauses"][0]["findings"][0]["explanation_es"]
    )


def test_only_explanations_are_sent_to_translator():
    translator = FakeTranslator()
    render_report(REPORT, "en", translator, GLOSSARY)
    assert set(translator.seen) == {"clause:0:0"}
    assert translator.seen["clause:0:0"] == "Contrato de locación con plazo mínimo."
    assert "CLÁUSULA" not in " ".join(translator.seen.values())


def test_spanish_legal_term_must_stay_in_parentheses():
    with pytest.raises(LLMInvalidOutput):
        render_report(REPORT, "en", FakeTranslator(keep_terms=False), GLOSSARY)


def test_glossary_terms_are_listed_with_translation():
    rendered = render_report(REPORT, "ru", FakeTranslator(), GLOSSARY)
    assert rendered["legal_terms"] == {"locación": "аренда"}
    assert "(locación)" in rendered["clauses"][0]["findings"][0]["explanation"]
