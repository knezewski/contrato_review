"""Errors of the contract intake stage. Codes match contracts/api.md §1."""


class IngestError(Exception):
    code = "INGEST_ERROR"


class UnsupportedFormat(IngestError):
    code = "UNSUPPORTED_FORMAT"


class DocumentUnreadable(IngestError):
    code = "DOCUMENT_UNREADABLE"


class NoClausesDetected(IngestError):
    code = "NO_CLAUSES_DETECTED"


class ContractTypeUndetected(IngestError):
    code = "CONTRACT_TYPE_UNDETECTED"


class SigningDateRequired(IngestError):
    code = "SIGNING_DATE_REQUIRED"


class OcrUnavailable(IngestError):
    code = "OCR_UNAVAILABLE"
