"""
Parent-child chunking strategy.

Takes a list of ParsedDocument (page-level text units) and produces
two tiers of chunks:

  • Parents  (~1200 tokens) — coarse context blocks.  These are what
    the LLM actually reads at generation time.
  • Children (~300 tokens, ~50 token overlap) — precision search targets.
    These get embedded and searched.  When a child is retrieved, the
    pipeline resolves child → parent_id → parent text for the LLM.

This two-tier approach gives the best of both worlds:
  - Small children → precise semantic matching during retrieval
  - Large parents  → the LLM gets enough surrounding context to
    produce grounded, coherent answers

All token counting uses tiktoken with the cl100k_base encoding
(same tokenizer family used by Cohere embed-english-v3.0).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import tiktoken

from app.config import settings
from app.parsers.base import ParsedDocument


# ── Tokenizer (module-level singleton) ──────────────────────────

_encoder = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    """Return the number of tokens in *text*."""
    return len(_encoder.encode(text, disallowed_special=()))


def _decode_tokens(token_ids: list[int]) -> str:
    """Decode a list of token IDs back to text."""
    return _encoder.decode(token_ids)


def _encode(text: str) -> list[int]:
    """Encode text to token IDs."""
    return _encoder.encode(text, disallowed_special=())


# ── Data classes ────────────────────────────────────────────────


@dataclass
class ChunkRecord:
    """
    Unified record for both parent and child chunks.
    Maps 1-to-1 with the Qdrant point payload schema defined in
    PROJECT_STRUCTURE.md.
    """

    chunk_id: str
    doc_id: str
    parent_id: str | None          # None for parents, parent's chunk_id for children
    chunk_type: str                 # "parent" | "child"
    source_filename: str
    page_number: int                # primary page (1-indexed)
    chunk_index: int                # sequential index within its tier
    chunk_text: str
    char_start: int
    char_end: int
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_payload(self) -> dict:
        """Serialise to the exact Qdrant payload schema."""
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "parent_id": self.parent_id,
            "chunk_type": self.chunk_type,
            "source_filename": self.source_filename,
            "page_number": self.page_number,
            "chunk_index": self.chunk_index,
            "chunk_text": self.chunk_text,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "created_at": self.created_at,
        }


# ── Internal: page-boundary aware text joining ──────────────────


@dataclass
class _PageSpan:
    """Tracks which page(s) a character range belongs to."""
    char_start: int
    char_end: int
    page_number: int


def _join_pages(pages: list[ParsedDocument]) -> tuple[str, list[_PageSpan]]:
    """
    Concatenate all page texts into one string, keeping a map of
    character offsets → page numbers so we can assign page_number
    to each chunk later.
    """
    parts: list[str] = []
    spans: list[_PageSpan] = []
    offset = 0

    for page in pages:
        text = page.text
        parts.append(text)
        spans.append(_PageSpan(
            char_start=offset,
            char_end=offset + len(text),
            page_number=page.page_number,
        ))
        offset += len(text) + 1  # +1 for the joining newline

    full_text = "\n".join(parts)
    return full_text, spans


def _page_for_offset(spans: list[_PageSpan], char_offset: int) -> int:
    """Return the page number that contains *char_offset*."""
    for span in spans:
        if span.char_start <= char_offset < span.char_end:
            return span.page_number
    # Fallback: return last page
    return spans[-1].page_number if spans else 1


# ── Core chunking logic ────────────────────────────────────────


def _split_text_by_tokens(
    full_text: str,
    max_tokens: int,
    overlap_tokens: int = 0,
) -> list[tuple[str, int, int]]:
    """
    Split *full_text* into chunks of at most *max_tokens* tokens,
    with *overlap_tokens* overlap between consecutive chunks.

    Returns a list of (chunk_text, char_start, char_end) tuples.
    """
    tokens = _encode(full_text)

    if not tokens:
        return []

    chunks: list[tuple[str, int, int]] = []
    step = max(1, max_tokens - overlap_tokens)
    i = 0

    while i < len(tokens):
        end = min(i + max_tokens, len(tokens))
        chunk_tokens = tokens[i:end]
        chunk_text = _decode_tokens(chunk_tokens)

        # Map token boundaries back to character offsets.
        # Decode the prefix to find char_start.
        prefix_text = _decode_tokens(tokens[:i])
        char_start = len(prefix_text)
        char_end = char_start + len(chunk_text)

        chunks.append((chunk_text.strip(), char_start, char_end))

        if end >= len(tokens):
            break
        i += step

    return chunks


def build_chunks(
    pages: list[ParsedDocument],
    doc_id: str,
    filename: str,
    parent_tokens: int | None = None,
    child_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> tuple[list[ChunkRecord], list[ChunkRecord]]:
    """
    Build parent and child chunks from parsed pages.

    Parameters
    ----------
    pages          : output of any parser (list of ParsedDocument)
    doc_id         : UUID of the uploaded document
    filename       : original filename
    parent_tokens  : max tokens per parent chunk (default from settings)
    child_tokens   : max tokens per child chunk  (default from settings)
    overlap_tokens : token overlap between adjacent child chunks
                     (default from settings)

    Returns
    -------
    (parent_chunks, child_chunks) — two lists of ChunkRecord.
    """
    parent_tokens = parent_tokens or settings.chunk_parent_tokens
    child_tokens = child_tokens or settings.chunk_child_tokens
    overlap_tokens = overlap_tokens or settings.chunk_overlap_tokens

    if not pages:
        return [], []

    # Step 1: join all pages into one continuous text + page map
    full_text, page_spans = _join_pages(pages)

    if not full_text.strip():
        return [], []

    # Step 2: split into parent-sized chunks (no overlap between parents)
    raw_parents = _split_text_by_tokens(full_text, parent_tokens, overlap_tokens=0)

    parents: list[ChunkRecord] = []
    children: list[ChunkRecord] = []
    child_index = 0

    for p_idx, (p_text, p_char_start, p_char_end) in enumerate(raw_parents):
        if not p_text.strip():
            continue

        parent_id = str(uuid.uuid4())
        parent_page = _page_for_offset(page_spans, p_char_start)

        parent = ChunkRecord(
            chunk_id=parent_id,
            doc_id=doc_id,
            parent_id=None,
            chunk_type="parent",
            source_filename=filename,
            page_number=parent_page,
            chunk_index=p_idx,
            chunk_text=p_text,
            char_start=p_char_start,
            char_end=p_char_end,
        )
        parents.append(parent)

        # Step 3: split each parent's text into child-sized chunks (with overlap)
        raw_children = _split_text_by_tokens(p_text, child_tokens, overlap_tokens)

        for c_text, c_local_start, c_local_end in raw_children:
            if not c_text.strip():
                continue

            # Map child's local offsets back to global document offsets
            c_global_start = p_char_start + c_local_start
            c_global_end = p_char_start + c_local_end
            child_page = _page_for_offset(page_spans, c_global_start)

            child = ChunkRecord(
                chunk_id=str(uuid.uuid4()),
                doc_id=doc_id,
                parent_id=parent_id,
                chunk_type="child",
                source_filename=filename,
                page_number=child_page,
                chunk_index=child_index,
                chunk_text=c_text,
                char_start=c_global_start,
                char_end=c_global_end,
            )
            children.append(child)
            child_index += 1

    return parents, children
