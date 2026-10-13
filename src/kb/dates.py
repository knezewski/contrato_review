"""Norm dates as int YYYYMMDD (constitution II, data-model.md §3).

Chroma compares only numbers in filters, so date strings are not stored.
An open `valid_to` is encoded with the sentinel 99991231. An empty string is an error, not a placeholder.
"""

from datetime import date

OPEN_END = 99991231


class DateParseError(ValueError):
    pass


def to_yyyymmdd(value: str | None, open_end: bool = False) -> int:
    if value is None:
        if open_end:
            return OPEN_END
        raise DateParseError("the start date cannot be empty")
    if value == "":
        raise DateParseError("an empty string is not allowed as a date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise DateParseError(f"invalid date: {value!r}") from exc
    return parsed.year * 10000 + parsed.month * 100 + parsed.day
