"""Analysis errors. Codes — contracts/api.md §1 (503 LLM_UNAVAILABLE, 502 LLM_INVALID_OUTPUT)."""


class ReviewError(Exception):
    code = "REVIEW_ERROR"


class LLMProviderError(Exception):
    """One failed provider call (network, timeout, 5xx). Retried."""


class LLMUnavailable(ReviewError):
    code = "LLM_UNAVAILABLE"


class LLMInvalidOutput(ReviewError):
    code = "LLM_INVALID_OUTPUT"
