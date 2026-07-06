"""
Upload router — POST /upload

Full ingestion pipeline:
  1. Validate file (extension, size)
  2. Upload raw bytes to Supabase Storage
  3. Parse into page-level units
  4. Chunk into parent + child tiers
  5. Embed children (dense via Cohere + sparse via fastembed)
  6. Upsert everything into Qdrant

Processing starts immediately upon upload — no deferred queues.
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.config import settings
from app.models.schemas import UploadResponse
from app.parsers.dispatcher import parse_file, SUPPORTED_EXTENSIONS
from app.storage.supabase_client import upload_raw_file
from app.chunking.parent_child import build_chunks
from app.embeddings.cohere_embed import embed_texts
from app.retrieval.sparse import embed_sparse
from app.storage.qdrant_client import (
    ensure_collection,
    upsert_child_chunks,
    upsert_parent_chunks,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["upload"])

# Map extensions to MIME types for Supabase upload
_MIME_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and fully process a document (PDF or DOCX only).

    The entire parse → chunk → embed → store pipeline runs
    synchronously so the response includes the final child chunk
    count and the document is immediately queryable.
    """
    # ── 1. Validate filename / extension ────────────────────────
    filename = file.filename or "unknown"
    ext = _get_extension(filename)

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Only {', '.join(sorted(SUPPORTED_EXTENSIONS))} are allowed."
            ),
        )

    # ── 2. Read bytes + validate size ───────────────────────────
    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(file_bytes) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large ({len(file_bytes) / 1024 / 1024:.1f} MB). "
                f"Maximum allowed: {settings.max_upload_size_mb} MB."
            ),
        )

    # ── 3. Assign a unique doc ID ───────────────────────────────
    doc_id = str(uuid.uuid4())
    logger.info("Processing upload: doc_id=%s, filename=%s", doc_id, filename)

    # ── 4. Upload raw file to Supabase Storage ──────────────────
    storage_path = f"{doc_id}/{filename}"
    content_type = _MIME_MAP.get(ext, "application/octet-stream")

    try:
        upload_raw_file(file_bytes, storage_path, content_type)
        logger.info("Raw file uploaded to Supabase: %s", storage_path)
    except Exception as e:
        logger.error("Supabase upload failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to upload file to storage: {e}",
        )

    # ── 5. Parse into page-level units ──────────────────────────
    try:
        parsed_pages = parse_file(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Parsing failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse document: {e}",
        )

    if not parsed_pages:
        raise HTTPException(
            status_code=400,
            detail="No text could be extracted from this document.",
        )

    logger.info("Parsed %d pages/sections from %s", len(parsed_pages), filename)

    # ── 6. Chunk into parent + child tiers ──────────────────────
    try:
        parents, children = build_chunks(parsed_pages, doc_id, filename)
    except Exception as e:
        logger.error("Chunking failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to chunk document: {e}",
        )

    logger.info(
        "Chunking complete: %d parents, %d children",
        len(parents),
        len(children),
    )

    if not children:
        raise HTTPException(
            status_code=400,
            detail="Document produced no searchable chunks after processing.",
        )

    # ── 7. Embed children (dense + sparse) ──────────────────────
    child_texts = [c.chunk_text for c in children]

    try:
        dense_vectors = embed_texts(child_texts)
        logger.info("Dense embeddings generated: %d vectors", len(dense_vectors))
    except Exception as e:
        logger.error("Dense embedding failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to generate dense embeddings: {e}",
        )

    try:
        sparse_vectors = embed_sparse(child_texts)
        logger.info("Sparse embeddings generated: %d vectors", len(sparse_vectors))
    except Exception as e:
        logger.error("Sparse embedding failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to generate sparse embeddings: {e}",
        )

    # ── 8. Upsert into Qdrant ───────────────────────────────────
    try:
        ensure_collection()
        upsert_parent_chunks(parents)
        upsert_child_chunks(children, dense_vectors, sparse_vectors)
        logger.info(
            "Qdrant upsert complete: %d parents + %d children",
            len(parents),
            len(children),
        )
    except Exception as e:
        logger.error("Qdrant upsert failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to store vectors in Qdrant: {e}",
        )

    # ── 9. Return response ──────────────────────────────────────
    return UploadResponse(
        doc_id=doc_id,
        filename=filename,
        chunk_count=len(children),
        message=(
            f"Processed {filename}: {len(parsed_pages)} pages → "
            f"{len(parents)} parent chunks → {len(children)} child chunks. "
            f"Document is now queryable."
        ),
    )


def _get_extension(filename: str) -> str:
    """Return lowercased extension including the dot."""
    _, ext = os.path.splitext(filename)
    return ext.lower()
