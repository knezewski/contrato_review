"""Model response schema for analyzing one clause (passed as JSON Schema to tool use)."""

from typing import Literal

from pydantic import BaseModel, Field


class FindingOut(BaseModel):
    type: Literal["risk", "gap", "mismatch"]
    level: Literal["low", "medium", "high"]
    explanation_es: str = Field(min_length=1)
    article_refs: list[str] = Field(default_factory=list)
    no_norm_found: bool = False


class ClauseReviewOutput(BaseModel):
    findings: list[FindingOut]
