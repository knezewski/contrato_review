"""Anthropic (Claude) client for clause analysis (research.md R3, R8).

- Structured response: tool use with the JSON Schema ClauseReviewOutput; the tool choice is forced.
- temperature=0; the model comes from the LLM_MODEL config.
- Retries for network and service errors: up to max_attempts attempts, pauses of 1 s and 3 s.
- SDK retries are disabled (max_retries=0): this module controls retries so that there is one shared limit.
- The API key is never logged; clause text and model responses are never written to the logs.
"""

from __future__ import annotations

import time
from pathlib import Path

import anthropic

from src.retrieval.retrieve import RetrievedNorm
from src.review.errors import LLMProviderError
from src.review.schema import ClauseReviewOutput

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "clause_review_es.md"
TOOL_NAME = "record_clause_review"
TRANSLATE_TOOL_NAME = "record_translation"
TRANSLATE_SYSTEM = (
    "Traduce los textos de análisis jurídico al idioma indicado. Conserva cada término jurídico español "
    "entre paréntesis justo después de su traducción, por ejemplo: arrendamiento (locación). "
    "No añadas opiniones ni datos. Responde solo mediante la herramienta indicada."
)
BACKOFF_S = (1.0, 3.0)


class AnthropicClaudeClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_s: float,
        max_attempts: int,
        client=None,
        sleep=time.sleep,
    ):
        self._model = model
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._system = PROMPT_PATH.read_text(encoding="utf-8")
        self._client = client or anthropic.Anthropic(
            api_key=api_key, timeout=timeout_s, max_retries=0
        )
        self._tool = {
            "name": TOOL_NAME,
            "description": "Registra el resultado del análisis de la cláusula.",
            "input_schema": ClauseReviewOutput.model_json_schema(),
        }
        self._translate_tool = {
            "name": TRANSLATE_TOOL_NAME,
            "description": "Registra las traducciones por identificador.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "translations": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    }
                },
                "required": ["translations"],
            },
        }

    def _user_message(
        self, clause_text: str, norms: list[RetrievedNorm], contract_type: str
    ) -> str:
        norm_lines = [
            f"- id: {n.id} | artículo {n.article} | {n.regime} | verbatim: {str(n.verbatim).lower()}\n  {n.text}"
            for n in norms
        ]
        return (
            f"Tipo de contrato: {contract_type}\n\n"
            f"Cláusula:\n{clause_text}\n\n"
            "Normas encontradas (usa solo estos ids en article_refs):\n"
            + "\n".join(norm_lines)
        )

    def review_clause(
        self, clause_text: str, norms: list[RetrievedNorm], contract_type: str
    ) -> dict:
        message = self._user_message(clause_text, norms, contract_type)
        last: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    temperature=0,
                    system=self._system,
                    tools=[self._tool],
                    tool_choice={"type": "tool", "name": TOOL_NAME},
                    messages=[{"role": "user", "content": message}],
                )
            except anthropic.APIError as exc:
                last = exc
                if attempt + 1 < self._max_attempts:
                    self._sleep(BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)])
                continue
            for block in response.content:
                if (
                    getattr(block, "type", None) == "tool_use"
                    and block.name == TOOL_NAME
                ):
                    return dict(block.input)
            return {}  # the model did not call the tool: an empty response fails the schema and is retried
        raise LLMProviderError(
            f"provider unavailable after {self._max_attempts} attempts"
        ) from last

    def translate(self, items: dict[str, str], lang: str) -> dict[str, str]:
        """Translates explanation texts (only `explanation_es`); keys are preserved."""
        language = {"en": "inglés", "ru": "ruso"}[lang]
        message = f"Idioma de destino: {language}\n\n" + "\n".join(
            f"{key}: {text}" for key, text in items.items()
        )
        last: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=2048,
                    temperature=0,
                    system=TRANSLATE_SYSTEM,
                    tools=[self._translate_tool],
                    tool_choice={"type": "tool", "name": TRANSLATE_TOOL_NAME},
                    messages=[{"role": "user", "content": message}],
                )
            except anthropic.APIError as exc:
                last = exc
                if attempt + 1 < self._max_attempts:
                    self._sleep(BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)])
                continue
            for block in response.content:
                if (
                    getattr(block, "type", None) == "tool_use"
                    and block.name == TRANSLATE_TOOL_NAME
                ):
                    return dict(block.input["translations"])
            return {}
        raise LLMProviderError(
            f"provider unavailable after {self._max_attempts} attempts"
        ) from last
