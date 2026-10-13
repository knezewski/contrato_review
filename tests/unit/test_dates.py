import pytest

from src.kb.dates import OPEN_END, DateParseError, to_yyyymmdd


def test_iso_date_becomes_int():
    assert to_yyyymmdd("2023-12-29") == 20231229


def test_open_end_becomes_sentinel():
    assert to_yyyymmdd(None, open_end=True) == OPEN_END == 99991231


def test_null_start_is_rejected():
    with pytest.raises(DateParseError):
        to_yyyymmdd(None, open_end=False)


def test_empty_string_is_rejected():
    with pytest.raises(DateParseError):
        to_yyyymmdd("", open_end=True)


@pytest.mark.parametrize("value", ["2023-02-30", "29/12/2023", "not-a-date"])
def test_invalid_dates_are_rejected(value):
    with pytest.raises(DateParseError):
        to_yyyymmdd(value)
