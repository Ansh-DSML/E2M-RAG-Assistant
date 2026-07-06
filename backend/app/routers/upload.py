"""
Upload router — POST /upload

Full ingestion pipeline with streaming progress:
  1. Validate file (extension, size)
  2. Upload raw bytes to Supabase Storage
  3. Parse into page-level units
  4. Chunk into parent + child tiers
  5. Embed children (dense via Cohere + sparse via fastembed)
  6. Upsert everything into Qdrant

Returns NDJSON (newline-delimited JSON) stream with progress events.
"""

from __future__ import annotations

import json
import logging
import os
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
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

_MIME_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _progress(step: str, status: str, message: str, **extra) -> str:
    event = {"step": step, "status": status, "message": message, **extra}
    return json.dumps(event) + "\n"


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    # Validate before streaming
    filename = file.filename or "unknown"
    ext = _get_extension(filename)

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Only {', '.join(sorted(SUPPORTED_EXTENSIONS))} are allowed.",
        )

    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(file_bytes) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(file_bytes) / 1024 / 1024:.1f} MB). Maximum: {settings.max_upload_size_mb} MB.",
        )

    doc_id = str(uuid.uuid4())
    storage_path = f"{doc_id}/{filename}"
    content_type = _MIME_MAP.get(ext, "application/octet-stream")

    def generate():
        # Step 1: Upload to Supabase
        yield _progress("uploading", "in_progress", "Uploading file to storage...")
        try:
            upload_raw_file(file_bytes, storage_path, content_type)
            yield _progress("uploading", "complete", "File uploaded to storage")
        except Exception as e:
            yield _progress("uploading", "error", f"Upload failed: {e}")
            return

        # Step 2: Parse
        yield _progress("parsing", "in_progress", "Parsing document pages...")
        try:
            parsed_pages = parse_file(file_bytes, filename)
            if not parsed_pages:
                yield _progress("parsing", "error", "No text could be extracted")
                return
            yield _progress("parsing", "complete", f"Parsed {len(parsed_pages)} pages", pages=len(parsed_pages))
        except Exception as e:
            yield _progress("parsing", "error", f"Parsing failed: {e}")
            return

        # Step 3: Chunk
        yield _progress("chunking", "in_progress", "Creating smart chunks...")
        try:
            parents, children = build_chunks(parsed_pages, doc_id, filename)
            if not children:
                yield _progress("chunking", "error", "No chunks created")
                return
            yield _progress("chunking", "complete", f"{len(parents)} parent + {len(children)} child chunks", parents=len(parents), children=len(children))
        except Exception as e:
            yield _progress("chunking", "error", f"Chunking failed: {e}")
            return

        # Step 4: Embed
        yield _progress("embedding", "in_progress", "Generating embeddings...")
        try:
            child_texts = [c.chunk_text for c in children]
            dense_vectors = embed_texts(child_texts)
            sparse_vectors = embed_sparse(child_texts)
            yield _progress("embedding", "complete", "Embeddings generated")
        except Exception as e:
            yield _progress("embedding", "error", f"Embedding failed: {e}")
            return

        # Step 5: Store in Qdrant
        yield _progress("storing", "in_progress", "Storing in vector database...")
        try:
            ensure_collection()
            upsert_parent_chunks(parents)
            upsert_child_chunks(children, dense_vectors, sparse_vectors)
            yield _progress("storing", "complete", "Vectors stored successfully")
        except Exception as e:
            yield _progress("storing", "error", f"Storage failed: {e}")
            return

        # Final event
        yield _progress(
            "done", "complete",
            f"Document ready! {len(children)} searchable chunks created.",
            doc_id=doc_id, filename=filename, chunk_count=len(children),
        )

    return StreamingResponse(generate(), media_type="application/x-ndjson")


def _get_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return ext.lower()
