"""
Dispatcher — routes a file to the correct parser based on extension.

Only PDF and DOCX are supported.
"""

from __future__ import annotations

from app.parsers.base import ParsedDocument
from app.parsers.pdf_parser import parse_pdf
from app.parsers.docx_parser import parse_docx


_PARSER_MAP = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
}

SUPPORTED_EXTENSIONS = set(_PARSER_MAP.keys())


def parse_file(file_bytes: bytes, filename: str) -> list[ParsedDocument]:
    """
    Detect the file type and delegate to the right parser.

    Parameters
    ----------
    file_bytes : raw bytes of the uploaded file
    filename   : original filename (used to detect extension)

    Returns
    -------
    List of ParsedDocument from the appropriate parser.

    Raises
    ------
    ValueError
        If the file extension is not supported.
    """
    ext = _get_extension(filename)

    parser_fn = _PARSER_MAP.get(ext)
    if parser_fn is None:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    return parser_fn(file_bytes, filename)


def _get_extension(filename: str) -> str:
    """Return the lowercased file extension including the dot."""
    import os
    _, ext = os.path.splitext(filename)
    return ext.lower()
