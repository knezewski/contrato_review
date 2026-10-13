import pytest

from src.ingest.errors import DocumentUnreadable, UnsupportedFormat
from src.ingest.extract import extract


def test_docx_text_extracted_without_ocr(fixture_bytes):
    doc = extract(fixture_bytes("locacion_2026_synthetic.docx"))
    assert doc.source_format == "docx"
    assert doc.needs_ocr is False
    assert "CLÁUSULA PRIMERA" in doc.text_es
    assert "15 días del mes de marzo de 2026" in doc.text_es


def test_pdf_with_text_layer_is_not_flagged(tmp_path):
    import pymupdf

    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "CONTRATO DE LOCACIÓN")
    data = pdf.tobytes()
    pdf.close()

    doc = extract(data)
    assert doc.source_format == "pdf"
    assert doc.needs_ocr is False
    assert "CONTRATO DE LOCACIÓN" in doc.text_es


def test_scanned_pdf_is_flagged_for_ocr(fixture_bytes):
    doc = extract(fixture_bytes("scan_no_text_synthetic.pdf"))
    assert doc.source_format == "pdf"
    assert doc.needs_ocr is True
    assert doc.ocr_applied is False
    assert doc.text_es.strip() == ""


def test_broken_pdf_is_unreadable(fixture_bytes):
    with pytest.raises(DocumentUnreadable):
        extract(fixture_bytes("unreadable_synthetic.pdf"))


def test_unknown_format_is_rejected():
    with pytest.raises(UnsupportedFormat):
        extract(b"# README\nplain text")
