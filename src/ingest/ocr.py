"""OCR fallback path for scans (spec clarifications; constitution, Technical Constraints).

Optional dependency: works only when OCR_ENABLED=true and a system tesseract with the spa language is present.
Otherwise OcrUnavailable (422 OCR_UNAVAILABLE) is raised; no partial report (AC12).
Pages are rendered in memory (pymupdf) and never written to disk.
"""

from __future__ import annotations

import shutil

from src.ingest.errors import OcrUnavailable


def ocr_pdf(data: bytes, lang: str = "spa") -> str:
    if shutil.which("tesseract") is None:
        raise OcrUnavailable("tesseract is not installed")
    from io import BytesIO

    import pymupdf
    import pytesseract
    from PIL import Image

    pages: list[str] = []
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        for page in pdf:
            pixmap = page.get_pixmap(dpi=300)
            image = Image.open(BytesIO(pixmap.tobytes("png")))
            pages.append(pytesseract.image_to_string(image, lang=lang))
    text = "\n".join(pages)
    if not text.strip():
        raise OcrUnavailable("OCR recognized no text")
    return text
