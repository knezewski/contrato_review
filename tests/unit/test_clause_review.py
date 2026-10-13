import pytest

from src.ingest.split import Clause
from src.retrieval.retrieve import RetrievedNorm
from src.review.clause_review import review_clause
from src.review.errors import LLMInvalidOutput, LLMProviderError, LLMUnavailable

CLAUSE = Clause(
    clause_id="c-01",
    marker="CLÁUSULA PRIMERA",
    heading="PRECIO",
    text_es="CLÁUSULA PRIMERA — PRECIO\nEl precio es $200.000.",
    position=0,
)


def _norm(norm_id="DNU 70/2023-1198", score=0.9):
    return RetrievedNorm(
        id=norm_id,
        jurisdiction="nacional",
        regime="DNU 70/2023",
        article="1198",
        title="Plazo",
        source_url="https://example.test",
        verbatim=False,
        text="Texto.",
        kind="norm",
        score=score,
    )


class FakeLLM:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def review_clause(self, clause_text, norms, contract_type):
        self.calls.append((clause_text, [n.id for n in norms], contract_type))
        item = self.outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


VALID = {
    "findings": [
        {
            "type": "risk",
            "level": "medium",
            "explanation_es": "Precio sin actualización.",
            "article_refs": ["DNU 70/2023-1198"],
            "no_norm_found": False,
        }
    ]
}


def test_valid_output_becomes_clause_review():
    llm = FakeLLM([VALID])
    review = review_clause(
        CLAUSE, [_norm()], llm, contract_type="locacion", threshold=0.3, max_attempts=3
    )
    assert review.clause_id == "c-01"
    assert review.findings[0].article_refs == ["DNU 70/2023-1198"]
    assert review.best_score == pytest.approx(0.9)
    assert review.needs_manual_review is False


def test_low_score_marks_manual_review():
    llm = FakeLLM([VALID])
    review = review_clause(
        CLAUSE,
        [_norm(score=0.2)],
        llm,
        contract_type="locacion",
        threshold=0.3,
        max_attempts=3,
    )
    assert review.needs_manual_review is True


def test_no_norms_gives_no_norm_status_without_llm_call():
    llm = FakeLLM([])
    review = review_clause(
        CLAUSE, [], llm, contract_type="locacion", threshold=0.3, max_attempts=3
    )
    assert llm.calls == []
    assert review.best_score is None
    assert review.needs_manual_review is True
    assert review.findings[0].type == "no_norm"
    assert review.findings[0].no_norm_found is True


def test_references_outside_retrieved_set_are_invalid_and_retried():
    bad = {
        "findings": [
            {
                "type": "risk",
                "level": "low",
                "explanation_es": "x",
                "article_refs": ["inventada-1"],
                "no_norm_found": False,
            }
        ]
    }
    llm = FakeLLM([bad, bad, bad])
    with pytest.raises(LLMInvalidOutput):
        review_clause(
            CLAUSE,
            [_norm()],
            llm,
            contract_type="locacion",
            threshold=0.3,
            max_attempts=3,
        )
    assert len(llm.calls) == 3


def test_schema_violation_is_invalid_output():
    llm = FakeLLM([{"findings": "no es lista"}, VALID])
    review = review_clause(
        CLAUSE, [_norm()], llm, contract_type="locacion", threshold=0.3, max_attempts=3
    )
    assert len(llm.calls) == 2
    assert review.findings[0].type == "risk"


def test_provider_failures_retry_then_unavailable():
    llm = FakeLLM(
        [
            LLMProviderError("timeout"),
            LLMProviderError("timeout"),
            LLMProviderError("timeout"),
        ]
    )
    with pytest.raises(LLMUnavailable):
        review_clause(
            CLAUSE,
            [_norm()],
            llm,
            contract_type="locacion",
            threshold=0.3,
            max_attempts=3,
        )
    assert len(llm.calls) == 3


def test_provider_failure_then_success_is_recovered():
    llm = FakeLLM([LLMProviderError("timeout"), VALID])
    review = review_clause(
        CLAUSE, [_norm()], llm, contract_type="locacion", threshold=0.3, max_attempts=3
    )
    assert review.findings[0].type == "risk"


def test_only_clause_text_and_norms_are_sent():
    llm = FakeLLM([VALID])
    review_clause(
        CLAUSE, [_norm()], llm, contract_type="locacion", threshold=0.3, max_attempts=3
    )
    sent_text, sent_norms, _ = llm.calls[0]
    assert sent_text == CLAUSE.text_es
    assert sent_norms == ["DNU 70/2023-1198"]
