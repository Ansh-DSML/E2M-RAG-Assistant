"""
Base data structures shared across all parsers.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedDocument:
    """
    One logical unit of extracted text from a source file.

    For PDFs this maps 1-to-1 with a page.
    For DOCX (which has no native page concept) this maps to a
    group of paragraphs with a synthetic section index.
    """

    text: str
    page_number: int  # 1-indexed page or section index
    source_file: str  # original filename, e.g. "report.pdf"
    metadata: dict = field(default_factory=dict)
