"""Splits a contract into clauses by legal markers (data-model.md §2).

Markers: `CLÁUSULA …`, `ARTÍCULO N`. Matching ignores case and diacritics.
The `N.` numbering is used ONLY if the document has no legal markers at all:
clauses contain nested lists `1. …`, which would otherwise become separate clauses.

Failure modes (constitution IV):
- A clause with no text after its marker is dropped and recorded in warnings.
- Text before the first marker is the preamble and is not part of the clauses.
- A document without markers → NoClausesDetected; the whole text is never treated as one clause.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from src.ingest.errors import NoClausesDetected

LEGAL_MARKER = re.compile(
    r"^\s*((?:CL[AÁ]USULA|ART[IÍ]CULO)\s+[^\n—:\-]{1,40}?)\s*(?:[—\-:]\s*(.*))?$",
    re.IGNORECASE | re.MULTILINE,
)
NUMBERED_MARKER = re.compile(r"^\s*(\d{1,2})\.\s+(.*)$", re.MULTILINE)


@dataclass
class Clause:
    clause_id: str
    marker: str
    heading: str | None
    text_es: str
    position: int


@dataclass
class SplitResult:
    preamble: str
    clauses: list[Clause]
    warnings: list[str] = field(default_factory=list)


def _normalize(text: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )


def _markers(text: str) -> list[tuple[int, int, str, str | None]]:
    """Returns (start, end of the marker line, marker, heading)."""
    found = []
    for match in LEGAL_MARKER.finditer(text):
        marker = " ".join(match.group(1).split())
        heading = (match.group(2) or "").strip() or None
        found.append((match.start(), match.end(), marker, heading))
    if found:
        return found
    for match in NUMBERED_MARKER.finditer(text):
        found.append(
            (
                match.start(),
                match.end(),
                f"{match.group(1)}.",
                match.group(2).strip() or None,
            )
        )
    return found


def split_contract(text_es: str) -> SplitResult:
    markers = _markers(text_es)
    if not markers:
        raise NoClausesDetected("no CLÁUSULA / ARTÍCULO / numbering marker found")

    preamble = text_es[: markers[0][0]].strip()
    clauses: list[Clause] = []
    warnings: list[str] = []
    for index, (start, _end, marker, heading) in enumerate(markers):
        stop = markers[index + 1][0] if index + 1 < len(markers) else len(text_es)
        block = text_es[start:stop].strip()
        body = block[len(block.split("\n", 1)[0]) :].strip() if "\n" in block else ""
        if not body and not heading:
            warnings.append(f"clause «{marker}» is empty and was dropped")
            continue
        clauses.append(
            Clause(
                clause_id=f"c-{len(clauses) + 1:02d}",
                marker=marker,
                heading=heading,
                text_es=block,
                position=index,
            )
        )
    return SplitResult(preamble=preamble, clauses=clauses, warnings=warnings)
