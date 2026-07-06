"""
Chat router — POST /chat

Runs the full RAG pipeline:
  1. Retrieval (hybrid search + rerank + parent resolution)
  2. Generation (Groq streaming)
  3. Source metadata

Streams the response via Server-Sent Events (SSE).
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import ChatRequest
from app.retrieval.rerank import retrieve
from app.generation.llm_groq import generate_stream
from app.storage.supabase_client import get_signed_url

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(request: ChatRequest):
    async def event_generator():
        # Step 1: Signal thinking
        yield {
            "event": "status",
            "data": json.dumps({"message": "Searching documents..."}),
        }

        # Step 2: Run retrieval (blocking, run in thread)
        result = await asyncio.to_thread(
            retrieve, query=request.query, doc_ids=request.doc_ids
        )

        if not result.children:
            yield {
                "event": "token",
                "data": json.dumps({"token": "I couldn't find any relevant information in the uploaded document to answer your question."}),
            }
            yield {"event": "sources", "data": json.dumps({"sources": []})}
            yield {"event": "done", "data": "{}"}
            return

        yield {
            "event": "status",
            "data": json.dumps({"message": "Generating response..."}),
        }

        # Step 3: Stream tokens from Groq via queue+thread
        context = result.context_for_llm

        q: queue.Queue = queue.Queue()

        def _run_generation():
            try:
                for token in generate_stream(request.query, context):
                    q.put(("token", token))
                q.put(("done", None))
            except Exception as e:
                q.put(("error", str(e)))

        thread = threading.Thread(target=_run_generation, daemon=True)
        thread.start()

        while True:
            try:
                msg_type, msg_data = await asyncio.to_thread(q.get, timeout=30)
            except Exception:
                break

            if msg_type == "token":
                yield {
                    "event": "token",
                    "data": json.dumps({"token": msg_data}),
                }
            elif msg_type == "done":
                break
            elif msg_type == "error":
                yield {
                    "event": "error",
                    "data": json.dumps({"error": msg_data}),
                }
                break

        thread.join(timeout=5)

        # Step 4: Send sources with signed URLs
        sources = []
        for child in result.children:
            # Generate signed URL for original file
            storage_path = f"{child.doc_id}/{child.source_filename}"
            try:
                signed_url = get_signed_url(storage_path)
            except Exception:
                signed_url = None

            sources.append({
                "chunk_id": child.chunk_id,
                "doc_id": child.doc_id,
                "source_filename": child.source_filename,
                "page_number": child.page_number,
                "text_snippet": child.chunk_text[:200],
                "score": round(child.score, 4),
                "signed_url": signed_url,
            })

        yield {
            "event": "sources",
            "data": json.dumps({"sources": sources}),
        }

        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_generator())
