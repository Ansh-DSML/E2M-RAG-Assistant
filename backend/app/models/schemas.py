"""
Pydantic models (schemas) shared across the API.

These define the shape of every request / response so FastAPI
auto-generates correct OpenAPI docs and validates payloads.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Upload ──────────────────────────────────────────────────────


class UploadResponse(BaseModel):
    """Returned after a successful document upload + processing."""

    doc_id: str = Field(..., description="UUID assigned to the uploaded document")
    filename: str = Field(..., description="Original filename")
    chunk_count: int = Field(..., description="Total child chunks created")
    message: str = Field(default="Document uploaded and processed successfully")


# ── Chat ────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Incoming chat question tied to a specific document."""

    doc_ids: list[str] = Field(..., description="UUIDs of the documents to query against")
    query: str = Field(..., min_length=1, description="User's natural-language question")


class SourceChunk(BaseModel):
    """
    One retrieved source chunk surfaced to the user for verification.
    Powers the "View Sources" panel in the frontend.
    """

    chunk_id: str = Field(..., description="UUID of the child chunk")
    doc_id: str = Field(..., description="UUID of the parent document")
    source_filename: str = Field(..., description="Original filename (e.g. report.pdf)")
    page_number: int | None = Field(None, description="Page number in the original doc")
    text_snippet: str = Field(..., description="Short excerpt from the chunk text")
    score: float = Field(..., description="Relevance score (post-rerank)")
    signed_url: str | None = Field(
        None,
        description="Signed Supabase URL to view the original file",
    )


class ChatResponse(BaseModel):
    """Full (non-streaming) chat response with answer + sources."""

    answer: str = Field(..., description="LLM-generated answer with citations")
    sources: list[SourceChunk] = Field(
        default_factory=list,
        description="Retrieved source chunks for verification",
    )
