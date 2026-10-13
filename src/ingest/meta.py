"""Contract type and signing date (data-model.md §2, ContractMeta).

Failure modes (constitution IV):
- Type: first the heading (the first non-empty lines), then a count of party words.
  If the heading contains neither «locación» nor «compraventa» and the counts are equal, the type is undetermined (None).
- Date: only the form «a los N días del mes de <month> de YYYY». The «N/N/YYYY» form is not recognized.
  If several different dates are found, the date is undetermined (None) and a warning is recorded:
  the user must provide the date (AC13).
- A date from the user's request takes priority; any conflict with the text is recorded in warnings.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
DATE_PATTERN = re.compile(
    r"a los (\d{1,2}) d[ií]as del mes de ([a-záéíóúñ]+) de (\d{4})", re.IGNORECASE
)
LEASE_WORDS = ("locacion", "locador", "locatario")
SALE_WORDS = ("compraventa", "vendedor", "comprador")


@dataclass
class ContractMeta:
    contract_type: str | None
    contract_type_source: str | None
    signing_date: date | None
    signing_date_source: str | None  # "detected" | "user_provided" | None
    warnings: list[str] = field(default_factory=list)


def _fold(text: str) -> str:
    """Lowercase without diacritics, for comparison."""
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(ch)
    )


def _detect_type(text: str) -> tuple[str | None, str | None]:
    head = " ".join(line for line in text.splitlines() if line.strip())[:300]
    folded_head = _fold(head)
    if "locacion" in folded_head:
        return "locacion", head[:80]
    if "compraventa" in folded_head:
        return "compraventa", head[:80]
    folded = _fold(text)
    lease = sum(folded.count(word) for word in LEASE_WORDS)
    sale = sum(folded.count(word) for word in SALE_WORDS)
    if lease > sale:
        return "locacion", "party word count"
    if sale > lease:
        return "compraventa", "party word count"
    return None, None


def _detect_dates(text: str) -> set[date]:
    found = set()
    for day, month_name, year in DATE_PATTERN.findall(_fold(text)):
        month = MONTHS.get(month_name)
        if month is None:
            continue
        try:
            found.add(date(int(year), month, int(day)))
        except ValueError:
            continue
    return found


def detect_meta(text_es: str, user_signing_date: date | None = None) -> ContractMeta:
    contract_type, type_source = _detect_type(text_es)
    warnings: list[str] = []

    detected = _detect_dates(text_es)
    signing_date: date | None = None
    source: str | None = None
    if len(detected) == 1:
        signing_date = detected.pop()
        source = "detected"
    elif len(detected) > 1:
        warnings.append(
            "several signing dates found in the text; the date is ambiguous"
        )

    if user_signing_date is not None:
        if signing_date is not None and signing_date != user_signing_date:
            warnings.append(
                f"the date from the request {user_signing_date.isoformat()} differs from the one found in the text "
                f"{signing_date.isoformat()}; the request's date takes priority"
            )
        signing_date = user_signing_date
        source = "user_provided"

    return ContractMeta(
        contract_type=contract_type,
        contract_type_source=type_source,
        signing_date=signing_date,
        signing_date_source=source,
        warnings=warnings,
    )
