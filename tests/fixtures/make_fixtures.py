"""Generates SYNTHETIC contracts for tests and the quickstart (constitution V: no personal data).

Run from the repository root:
    .venv/bin/python tests/fixtures/make_fixtures.py
"""

from pathlib import Path

import docx
import pymupdf

OUT = Path(__file__).resolve().parent


def _contract_lines(
    title: str,
    date_line: str,
    clauses: list[tuple[str, str]],
    include_price: bool = True,
) -> list[str]:
    lines = [title, "", "Entre las partes, conforme a las cláusulas siguientes:", ""]
    lines.append(date_line)
    lines.append("")
    for marker, body in clauses:
        lines.append(marker)
        lines.append(body)
        lines.append("")
    if not include_price:
        lines = [line for line in lines if "precio" not in line.lower()]
    return lines


LOCACION_CLAUSES = [
    (
        "CLÁUSULA PRIMERA — OBJETO",
        "El locador da en locación a el locatario el inmueble ubicado en calle Ejemplo 1234, CABA.",
    ),
    (
        "CLÁUSULA SEGUNDA — PLAZO",
        "El plazo de la locación es de dos (2) años desde el 1 de abril de 2026.",
    ),
    (
        "CLÁUSULA TERCERA — PRECIO",
        "El precio mensual de la locación es de pesos doscientos mil ($200.000).",
    ),
    (
        "CLÁUSULA CUARTA — ACTUALIZACIÓN",
        "El precio se actualiza cada seis (6) meses según índice acordado.",
    ),
    (
        "CLÁUSULA QUINTA — DESTINO",
        "El inmueble se destina exclusivamente a vivienda permanente.",
    ),
    (
        "CLÁUSULA SEXTA — EXPENSAS",
        "Las expensas ordinarias están a cargo del locatario.",
    ),
    (
        "CLÁUSULA SÉPTIMA — DEPÓSITO",
        "El locatario entrega un depósito en garantía equivalente a un mes de alquiler.",
    ),
    (
        "CLÁUSULA OCTAVA — RESOLUCIÓN ANTICIPADA",
        "El locatario puede resolver el contrato con preaviso de tres (3) meses.",
    ),
    (
        "CLÁUSULA NOVENA — DOMICILIOS",
        "Las partes constituyen domicilio en los indicados en el encabezado.",
    ),
    (
        "CLÁUSULA DÉCIMA — JURISDICCIÓN",
        "Para cualquier controversia son competentes los tribunales de la Ciudad Autónoma de Buenos Aires.",
    ),
]


def make_docx(name: str, lines: list[str]) -> None:
    document = docx.Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(OUT / name)


def make_scan_pdf(name: str) -> None:
    # A page without a text layer: graphics only.
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.draw_rect(
        pymupdf.Rect(72, 72, 300, 300), color=(0, 0, 0), fill=(0.8, 0.8, 0.8)
    )
    pdf.save(OUT / name)
    pdf.close()


def main() -> None:
    make_docx(
        "locacion_2026_synthetic.docx",
        _contract_lines(
            "CONTRATO DE LOCACIÓN DE VIVIENDA",
            "En la Ciudad Autónoma de Buenos Aires, a los 15 días del mes de marzo de 2026.",
            LOCACION_CLAUSES,
        ),
    )
    make_docx(
        "locacion_2022_synthetic.docx",
        _contract_lines(
            "CONTRATO DE LOCACIÓN DE VIVIENDA",
            "En la Ciudad Autónoma de Buenos Aires, a los 10 días del mes de octubre de 2022.",
            LOCACION_CLAUSES,
        ),
    )
    make_docx(
        "locacion_no_price_synthetic.docx",
        _contract_lines(
            "CONTRATO DE LOCACIÓN DE VIVIENDA",
            "En la Ciudad Autónoma de Buenos Aires, a los 15 días del mes de marzo de 2026.",
            [c for c in LOCACION_CLAUSES if "PRECIO" not in c[0]],
            include_price=False,
        ),
    )
    make_docx(
        "compraventa_2025_synthetic.docx",
        _contract_lines(
            "BOLETO DE COMPRAVENTA DE INMUEBLE",
            "En la Ciudad Autónoma de Buenos Aires, a los 20 días del mes de junio de 2025.",
            [
                (
                    "CLÁUSULA PRIMERA — OBJETO",
                    "El vendedor vende al comprador la unidad funcional ubicada en calle Ejemplo 99, CABA.",
                ),
                (
                    "CLÁUSULA SEGUNDA — PRECIO",
                    "El precio de la compraventa es de dólares ciento cincuenta mil (USD 150.000).",
                ),
                (
                    "CLÁUSULA TERCERA — ESCRITURA",
                    "La escritura se otorgará dentro de los sesenta (60) días.",
                ),
            ],
        ),
    )
    make_docx(
        "no_date_synthetic.docx",
        _contract_lines(
            "CONTRATO DE LOCACIÓN DE VIVIENDA",
            "Las partes firman el presente documento.",
            LOCACION_CLAUSES[:3],
        ),
    )
    make_docx(
        "no_clauses_synthetic.docx",
        [
            "Texto libre sin marcadores de cláusula.",
            "El precio se pagará mensualmente.",
        ],
    )
    make_scan_pdf("scan_no_text_synthetic.pdf")
    (OUT / "unreadable_synthetic.pdf").write_bytes(
        b"%PDF-1.4\n%truncated garbage without xref"
    )


if __name__ == "__main__":
    main()
