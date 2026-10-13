"""Фиксированные тексты дисклеймера и заголовков (AC11, R12). Не переводятся моделью.

Три утверждения AC11: (a) юридически обязателен только испанский оригинал; (b) отчёт информационный;
(c) окончательное решение принимает квалифицированный юрист.
"""

DISCLAIMER = {
    "es": (
        "Este informe es informativo. Solo el texto original en español es jurídicamente vinculante. "
        "La determinación final la realiza un abogado calificado."
    ),
    "en": (
        "This report is informational. Only the original Spanish text is legally binding. "
        "The final determination is made by a qualified lawyer."
    ),
    "ru": (
        "Этот отчёт носит информационный характер. Юридически обязывает только испанский оригинал. "
        "Окончательное решение принимает квалифицированный юрист."
    ),
}

LABELS = {
    "es": {
        "title": "Informe de revisión del contrato",
        "clause": "Cláusula",
        "gaps": "Omisiones",
        "manual": "Revisión manual",
        "stamp": "Impuesto de sellos (CABA)",
        "regime": "Régimen aplicable",
    },
    "en": {
        "title": "Contract review report",
        "clause": "Clause",
        "gaps": "Gaps",
        "manual": "Manual review",
        "stamp": "Stamp tax (CABA)",
        "regime": "Applicable regime",
    },
    "ru": {
        "title": "Отчёт о проверке договора",
        "clause": "Пункт",
        "gaps": "Пробелы",
        "manual": "Ручная проверка",
        "stamp": "Гербовый сбор (CABA)",
        "regime": "Применимый режим",
    },
}
