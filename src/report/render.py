"""Report in a language (T7; AC8, AC11, AC16; research.md R12).

Input: the language-neutral report (dict from Report.model_dump). For `es` no translation is called.
For `en`/`ru` only the `explanation_es` texts and identifiers are sent to the translator — never the contract text.
Spanish legal terms from the glossary must stay in brackets next to the translation;
if the model drops them, the translation is rejected (LLMInvalidOutput); there is no partial result.
The disclaimer and labels are fixed texts from report/i18n; the model does not translate them.
"""

from __future__ import annotations

import unicodedata

from src.report.i18n.disclaimer import DISCLAIMER, LABELS
from src.review.errors import LLMInvalidOutput, LLMProviderError, LLMUnavailable

SUPPORTED = ("es", "en", "ru")


def _fold(text: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(ch)
    )


def _terms_in(text: str, glossary: list[dict]) -> list[str]:
    haystack = _fold(text)
    return [entry["es"] for entry in glossary if _fold(entry["es"]) in haystack]


def _collect(report: dict) -> dict[str, str]:
    items: dict[str, str] = {}
    for ci, clause in enumerate(report["clauses"]):
        for fi, finding in enumerate(clause["findings"]):
            items[f"clause:{ci}:{fi}"] = finding["explanation_es"]
    for gi, gap in enumerate(report.get("contract_gaps", [])):
        items[f"gap:{gi}"] = gap["explanation_es"]
    return items


def render_report(report: dict, lang: str, translator, glossary: list[dict]) -> dict:
    if lang not in SUPPORTED:
        raise ValueError(f"unsupported language: {lang}")
    source = _collect(report)

    if lang == "es":
        translated = dict(source)
        terms_by_key: dict[str, list[str]] = {}
    else:
        terms_by_key = {key: _terms_in(text, glossary) for key, text in source.items()}
        try:
            translated = translator.translate(source, lang) if source else {}
        except LLMProviderError as exc:
            raise LLMUnavailable("translation unavailable") from exc
        for key, terms in terms_by_key.items():
            text = translated.get(key)
            if text is None:
                raise LLMInvalidOutput(f"translation is missing item {key}")
            for term in terms:
                if f"({term})" not in text:
                    raise LLMInvalidOutput(
                        f"the translation of {key} lost the term «{term}» in brackets"
                    )

    def _finding(ci: int, fi: int, finding: dict) -> dict:
        return {
            "type": finding["type"],
            "level": finding["level"],
            "explanation": translated[f"clause:{ci}:{fi}"],
            "article_refs": finding["article_refs"],
            "no_norm_found": finding["no_norm_found"],
            "source": finding["source"],
            "needs_manual_review": finding["needs_manual_review"],
        }

    clauses = []
    for ci, clause in enumerate(report["clauses"]):
        clauses.append(
            {
                "clause_id": clause["clause_id"],
                "marker": clause["marker"],
                "heading": clause["heading"],
                "needs_manual_review": clause["needs_manual_review"],
                "article_refs": clause["article_refs"],
                "findings": [
                    _finding(ci, fi, f) for fi, f in enumerate(clause["findings"])
                ],
            }
        )

    gaps = []
    for gi, gap in enumerate(report.get("contract_gaps", [])):
        gaps.append(
            {
                "type": gap["type"],
                "level": gap["level"],
                "explanation": translated[f"gap:{gi}"],
                "article_refs": gap["article_refs"],
                "source": gap["source"],
                "needs_manual_review": gap["needs_manual_review"],
                "searched_patterns": gap["searched_patterns"],
            }
        )

    legal_terms = {}
    if lang != "es":
        by_es = {entry["es"]: entry.get(lang) for entry in glossary}
        for terms in terms_by_key.values():
            for term in terms:
                if by_es.get(term):
                    legal_terms[term] = by_es[term]

    return {
        "lang": lang,
        "source_language": "es",
        "title": LABELS[lang]["title"],
        "labels": LABELS[lang],
        "disclaimer": DISCLAIMER[lang],
        "contract_type": report["contract_type"],
        "signing_date": report["signing_date"],
        "regime": report["regime"],
        "summary": report["summary"],
        "clauses": clauses,
        "contract_gaps": gaps,
        "stamp_tax": report["stamp_tax"],
        "warnings": report["warnings"],
        "legal_terms": legal_terms,
    }
