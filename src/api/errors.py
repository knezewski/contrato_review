"""Single error format (contracts/api.md §4) and the mapping from exception to HTTP code.

Error bodies contain no contract text; messages are short, in Spanish and English.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.ingest.errors import (
    ContractTypeUndetected,
    DocumentUnreadable,
    IngestError,
    NoClausesDetected,
    OcrUnavailable,
    SigningDateRequired,
    UnsupportedFormat,
)
from src.review.errors import LLMInvalidOutput, LLMUnavailable, ReviewError


@dataclass
class ApiError(Exception):
    status: int
    code: str
    message: str
    message_en: str


MESSAGES = {
    "UNSUPPORTED_FORMAT": (
        415,
        "Formato no admitido. Suba un archivo PDF o DOCX.",
        "Unsupported format. Upload a PDF or DOCX file.",
    ),
    "FILE_TOO_LARGE": (
        413,
        "El archivo supera el tamaño máximo permitido.",
        "The file exceeds the maximum allowed size.",
    ),
    "DOCUMENT_UNREADABLE": (
        422,
        "No se pudo leer el documento. Compruebe que el archivo no esté dañado.",
        "The document could not be read. Check that the file is not corrupted.",
    ),
    "OCR_UNAVAILABLE": (
        422,
        "El documento es un escaneo sin texto y el reconocimiento óptico no está disponible.",
        "The document is a scan without a text layer and OCR is not available.",
    ),
    "NO_CLAUSES_DETECTED": (
        422,
        "No se encontraron cláusulas (CLÁUSULA, ARTÍCULO o numeración).",
        "No clauses were found (CLÁUSULA, ARTÍCULO or numbering).",
    ),
    "CONTRACT_TYPE_UNDETECTED": (
        422,
        "No se pudo determinar si es compraventa o locación.",
        "Could not determine whether this is a sale or a lease.",
    ),
    "SIGNING_DATE_REQUIRED": (
        422,
        "No se pudo detectar la fecha de firma. Indique la fecha (YYYY-MM-DD) y vuelva a enviar el archivo.",
        "Signing date could not be detected. Provide it as signing_date (YYYY-MM-DD) and resubmit.",
    ),
    "SIGNING_DATE_INVALID": (
        422,
        "La fecha de firma no es válida o está en el futuro.",
        "The signing date is invalid or in the future.",
    ),
    "LANG_UNSUPPORTED": (
        422,
        "Idioma no admitido. Use es, en o ru.",
        "Unsupported language. Use es, en or ru.",
    ),
    "LLM_UNAVAILABLE": (
        503,
        "El servicio de análisis no está disponible. Intente de nuevo más tarde.",
        "The analysis service is unavailable. Try again later.",
    ),
    "LLM_INVALID_OUTPUT": (
        502,
        "El servicio de análisis devolvió una respuesta no válida.",
        "The analysis service returned an invalid response.",
    ),
    "REPORT_NOT_FOUND": (
        404,
        "Informe no encontrado o vencido.",
        "Report not found or expired.",
    ),
    "REPORT_STORE_FAILED": (
        500,
        "No se pudo guardar el informe.",
        "The report could not be saved.",
    ),
}


def api_error(code: str) -> ApiError:
    status, message, message_en = MESSAGES[code]
    return ApiError(status=status, code=code, message=message, message_en=message_en)


def map_exception(exc: Exception) -> ApiError | None:
    if isinstance(exc, ApiError):
        return exc
    if isinstance(exc, UnsupportedFormat):
        return api_error("UNSUPPORTED_FORMAT")
    if isinstance(exc, DocumentUnreadable):
        return api_error("DOCUMENT_UNREADABLE")
    if isinstance(exc, OcrUnavailable):
        return api_error("OCR_UNAVAILABLE")
    if isinstance(exc, NoClausesDetected):
        return api_error("NO_CLAUSES_DETECTED")
    if isinstance(exc, ContractTypeUndetected):
        return api_error("CONTRACT_TYPE_UNDETECTED")
    if isinstance(exc, SigningDateRequired):
        return api_error("SIGNING_DATE_REQUIRED")
    if isinstance(exc, LLMUnavailable):
        return api_error("LLM_UNAVAILABLE")
    if isinstance(exc, LLMInvalidOutput):
        return api_error("LLM_INVALID_OUTPUT")
    if isinstance(exc, (IngestError, ReviewError)):
        return api_error("DOCUMENT_UNREADABLE")
    return None
