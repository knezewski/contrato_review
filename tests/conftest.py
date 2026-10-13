from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixture_bytes():
    """Reads a synthetic file from tests/fixtures/ by name."""

    def _read(name: str) -> bytes:
        return (FIXTURES_DIR / name).read_bytes()

    return _read
