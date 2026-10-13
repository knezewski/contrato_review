"""Interface of the generative model for clause analysis and translation (research.md R3, R12).

An implementation receives only the clause text and the norms (analysis) or the result fields (translation).
The raw contract text is never passed for translation.
"""

from __future__ import annotations

from typing import Protocol

from src.retrieval.retrieve import RetrievedNorm


class ClauseLLM(Protocol):
    def review_clause(
        self, clause_text: str, norms: list[RetrievedNorm], contract_type: str
    ) -> dict:
        """Returns a raw response compatible with ClauseReviewOutput. Raises LLMProviderError on a provider failure."""
        ...
