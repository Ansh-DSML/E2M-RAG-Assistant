"""
PDF parser — page-by-page text extraction via PyMuPDF (fitz).

Preserves page_number so downstream citation can say
"Based on page 3 of report.pdf".
"""

from __future__ import annotations

import fitz  # PyMuPDF

from app.parsers.base import ParsedDocument


def parse_pdf(file_bytes: bytes, filename: str) -> list[ParsedDocument]:
    """
    Extract text from every page of a PDF.

    Parameters
    ----------
    file_bytes : raw bytes of the uploaded PDF
    filename   : original filename (for metadata)

    Returns
    -------
    List of ParsedDocument, one per page that contains text.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages: list[ParsedDocument] = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text").strip()

        if not text:
            continue  # skip blank pages (scanned images, cover art, etc.)

        pages.append(
            ParsedDocument(
                text=text,
                page_number=page_num + 1,  # 1-indexed for human display
                source_file=filename,
            )
        )

    doc.close()
    return pages
