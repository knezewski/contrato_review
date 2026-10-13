from types import SimpleNamespace

import anthropic
import httpx
import pytest

from src.retrieval.retrieve import RetrievedNorm
from src.review.errors import LLMProviderError
from src.review.llm.anthropic_client import TOOL_NAME, AnthropicClaudeClient


def _norm():
    return RetrievedNorm(
        id="DNU 70/2023-1198",
        jurisdiction="nacional",
        regime="DNU 70/2023",
        article="1198",
        title="Plazo",
        source_url="https://example.test",
        verbatim=False,
        text="Texto de la norma.",
        kind="norm",
        score=0.9,
    )


def _connection_error():
    request = httpx.Request("POST", "https://api.anthropic.test/v1/messages")
    return anthropic.APIConnectionError(request=request)


def _tool_response(payload):
    return SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name=TOOL_NAME, input=payload)]
    )


class FakeMessages:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeSdk:
    def __init__(self, results):
        self.messages = FakeMessages(results)


def _client(results, sleeps):
    return AnthropicClaudeClient(
        api_key="test-key",
        model="claude-sonnet-5-5",
        timeout_s=5,
        max_attempts=3,
        client=FakeSdk(results),
        sleep=sleeps.append,
    )


def test_returns_tool_input_and_forces_the_tool():
    sleeps = []
    payload = {"findings": []}
    client = _client([_tool_response(payload)], sleeps)
    assert (
        client.review_clause("CLÁUSULA PRIMERA — OBJETO\nTexto.", [_norm()], "locacion")
        == payload
    )
    call = client._client.messages.calls[0]
    assert call["temperature"] == 0
    assert call["model"] == "claude-sonnet-5-5"
    assert call["tool_choice"] == {"type": "tool", "name": TOOL_NAME}
    assert sleeps == []


def test_request_carries_clause_and_norms_only():
    sleeps = []
    client = _client([_tool_response({"findings": []})], sleeps)
    client.review_clause(
        "CLÁUSULA PRIMERA — OBJETO\nTexto del pacto.", [_norm()], "locacion"
    )
    user = client._client.messages.calls[0]["messages"][0]["content"]
    assert "Texto del pacto." in user
    assert "DNU 70/2023-1198" in user
    assert "CLÁUSULA SEGUNDA" not in user


def test_connection_errors_retry_with_backoff_then_succeed():
    sleeps = []
    client = _client(
        [_connection_error(), _connection_error(), _tool_response({"findings": []})],
        sleeps,
    )
    assert client.review_clause("Texto.", [_norm()], "locacion") == {"findings": []}
    assert sleeps == [1.0, 3.0]


def test_exhausted_attempts_raise_provider_error():
    sleeps = []
    client = _client(
        [_connection_error(), _connection_error(), _connection_error()], sleeps
    )
    with pytest.raises(LLMProviderError):
        client.review_clause("Texto.", [_norm()], "locacion")
    assert len(client._client.messages.calls) == 3


def test_missing_tool_call_returns_empty_dict_for_validation_to_reject():
    sleeps = []
    client = _client(
        [SimpleNamespace(content=[SimpleNamespace(type="text", text="hola")])], sleeps
    )
    assert client.review_clause("Texto.", [_norm()], "locacion") == {}
