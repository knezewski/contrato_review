"""Missing mandatory elements — deterministic check (research.md R10, AC17).

For each required_element from the KB, patterns (regex) are searched across the WHOLE contract text, including the preamble.
Matching ignores case and diacritics. No match → a heuristic gap for manual review.

Failure modes (constitution IV):
- false negatives: a pattern matched unrelated text → the gap is not raised;
- false positives: the element is present but worded differently or in an annex → the gap is raised with a review flag;
- no external calls: the contract text never leaves the process.
The patterns themselves are checked by tests on synthetic contracts (tests/unit/test_gaps.py).
"""

from __future__ import annotations

import re
import unicodedata

from src.report.model import Finding


def _fold(text: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(ch)
    )


def find_gaps(text_es: str, elements: list[dict]) -> list[Finding]:
    haystack = _fold(text_es)
    gaps: list[Finding] = []
    for element in elements:
        patterns = element["patterns"]
        for pattern in patterns:
            re.compile(pattern)  # a pattern error must be visible, not silently skipped
        if any(re.search(_fold(pattern), haystack) for pattern in patterns):
            continue
        gaps.append(
            Finding(
                type="gap",
                level=element["level"],
                explanation_es=(
                    f"No se encontró indicio de «{element['element']}» en el contrato. "
                    "Verificar manualmente."
                ),
                article_refs=[element["id"]],
                source="heuristic",
                needs_manual_review=True,
                searched_patterns=list(patterns),
            )
        )
    return gaps
