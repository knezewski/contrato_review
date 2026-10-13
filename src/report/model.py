"""Analysis and report models (data-model.md §4–§6).

The constitution I rule is implemented here: a finding that makes a legal claim must cite a norm
or state explicitly that no norm was found. The check of references against the found norms is ensure_refs_allowed.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, computed_field, model_validator

FindingType = Literal["risk", "gap", "mismatch", "no_norm"]
Level = Literal["low", "medium", "high"]


class Finding(BaseModel):
    """`no_norm` — the status «no norm found» (AC7), not a legal conclusion."""

    type: FindingType
    level: Level
    explanation_es: str
    article_refs: list[str] = Field(default_factory=list)
    no_norm_found: bool = False
    source: Literal["llm", "heuristic"] = "llm"
    needs_manual_review: bool = False
    searched_patterns: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_references(self):
        has_refs = bool(self.article_refs)
        if self.type == "no_norm":
            if has_refs or not self.no_norm_found:
                raise ValueError(
                    "no_norm allows only no_norm_found=true without references"
                )
            return self
        if has_refs == self.no_norm_found:
            raise ValueError(
                "either a norm reference or no_norm_found=true is required (not both, not neither)"
            )
        if self.source == "heuristic":
            if self.type != "gap":
                raise ValueError("heuristics are allowed only for gap")
            if len(self.article_refs) != 1:
                raise ValueError(
                    "a heuristic gap references exactly one required_element"
                )
            if not self.needs_manual_review:
                raise ValueError("a heuristic gap is always flagged for manual review")
            if not self.searched_patterns:
                raise ValueError("a heuristic gap must list the patterns searched")
        return self


def ensure_refs_allowed(finding: Finding, allowed_ids: set[str]) -> None:
    unknown = [ref for ref in finding.article_refs if ref not in allowed_ids]
    if unknown:
        raise ValueError(f"references outside the found norms: {unknown}")


class ClauseReview(BaseModel):
    clause_id: str
    marker: str
    heading: str | None = None
    findings: list[Finding]
    best_score: float | None
    needs_manual_review: bool
    retrieved_count: int

    @computed_field
    @property
    def article_refs(self) -> list[str]:
        refs: list[str] = []
        for finding in self.findings:
            for ref in finding.article_refs:
                if ref not in refs:
                    refs.append(ref)
        return refs


class StampTaxResult(BaseModel):
    contract_type: Literal["compraventa", "locacion"]
    applies: bool | None
    payer: Literal["buyer", "seller", "shared", "unknown"]
    vivienda_unica_exemption: bool | None
    amount_ars: Decimal | None
    rate_status: Literal["confirmed", "pending"]
    article_refs: list[str] = Field(default_factory=list)
    no_norm_found: bool = False
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _lease_has_no_amount(self):
        if self.contract_type == "locacion":
            if self.amount_ars is not None:
                raise ValueError("for locación no amount is computed (spec §3)")
            if self.rate_status != "pending":
                raise ValueError(
                    "for locación the rate is pending until Ley Tarifaria 2026 is confirmed"
                )
        return self


class RegimeInfo(BaseModel):
    regime: str
    valid_from_i: int
    valid_to_i: int


class Report(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    source_language: Literal["es"] = "es"
    disclaimer_key: Literal["informational_v1"] = "informational_v1"
    generated_at: datetime
    contract_type: Literal["compraventa", "locacion"]
    signing_date: date
    regime: RegimeInfo | None
    clause_count: int
    preamble_present: bool
    clauses: list[ClauseReview]
    contract_gaps: list[Finding] = Field(default_factory=list)
    stamp_tax: StampTaxResult | None = None
    summary: dict[str, int]
    warnings: list[str] = Field(default_factory=list)
