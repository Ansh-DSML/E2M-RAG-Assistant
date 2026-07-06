# Project Structure — Document-Based AI Assistant

Each file below is tagged with the **STAGE** (from EXECUTION_PLAN.md) it belongs to, and a one-line note on what goes in it. Build top-to-bottom, stage by stage — don't jump ahead.

```
rag-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   │     STAGE 1 — FastAPI app instance, CORS middleware, mount routers, health check route
│   │   │
│   │   ├── config.py
│   │   │     STAGE 1 — pydantic-settings class loading all .env vars, single source of truth for config
│   │   │
│   │   ├── models/
│   │   │   └── schemas.py
│   │   │         STAGE 1 — Pydantic models: UploadResponse, ChatRequest, ChatResponse,
│   │   │         SourceChunk (chunk_id, page_number, text_snippet, doc_filename, score)
│   │   │
│   │   ├── routers/
│   │   │   ├── upload.py
│   │   │   │     STAGE 2 — POST /upload : accept file, validate extension/size,
│   │   │   │     save to Supabase Storage, trigger parse→chunk→embed→store pipeline,
│   │   │   │     return doc_id + chunk count
│   │   │   │
│   │   │   └── chat.py
│   │   │         STAGE 5 — POST /chat : accept {doc_id, query}, run retrieval pipeline,
│   │   │         call Groq, stream tokens back (SSE or chunked response), attach sources
│   │   │
│   │   ├── parsers/
│   │   │   ├── base.py
│   │   │   │     STAGE 2 — ParsedDocument dataclass: {text, page_number, source_file}
│   │   │   │     one instance per "page" or logical unit
│   │   │   │
│   │   │   ├── pdf_parser.py
│   │   │   │     STAGE 2 — pymupdf (fitz): loop pages, extract text per page,
│   │   │   │     preserve page_number — this is what enables "Based on page 3"
│   │   │   │
│   │   │   ├── docx_parser.py
│   │   │   │     STAGE 2 — python-docx: extract paragraphs, no native page numbers,
│   │   │   │     so use a synthetic "section index" as page_number equivalent
│   │   │   │
│   │   │   ├── csv_parser.py
│   │   │   │     STAGE 2 — pandas: read rows, each row (or group of N rows) = one unit,
│   │   │   │     page_number = row range
│   │   │   │
│   │   │   ├── json_parser.py
│   │   │   │     STAGE 2 — flatten top-level keys/records into text blocks,
│   │   │   │     page_number = key path or record index
│   │   │   │
│   │   │   └── dispatcher.py
│   │   │         STAGE 2 — extension → correct parser function, raises on unsupported type
│   │   │
│   │   ├── chunking/
│   │   │   └── parent_child.py
│   │   │         STAGE 3 — takes List[ParsedDocument], builds:
│   │   │           parent chunks (~1200 tokens, coarse context)
│   │   │           child chunks (~300 tokens, nested inside each parent, +overlap)
│   │   │         each child stores parent_id; parents stored separately for lookup
│   │   │         at generation time
│   │   │
│   │   ├── embeddings/
│   │   │   └── cohere_embed.py
│   │   │         STAGE 3 — batch-embed all CHILD chunks via Cohere embed-english-v3.0
│   │   │         (input_type=search_document at index time,
│   │   │          input_type=search_query at query time — don't mix these up)
│   │   │
│   │   ├── storage/
│   │   │   ├── supabase_client.py
│   │   │   │     STAGE 2 — init Supabase client, upload_raw_file(), get_public_or_signed_url()
│   │   │   │     (signed URL is what powers "view original source" in frontend)
│   │   │   │
│   │   │   └── qdrant_client.py
│   │   │         STAGE 3 — init Qdrant client, create_collection() with named vectors
│   │   │         (dense: 1024-dim cosine, sparse: BM25-style), upsert_points(),
│   │   │         each point payload = full metadata schema (see below)
│   │   │
│   │   ├── retrieval/
│   │   │   ├── sparse.py
│   │   │   │     STAGE 4 — fastembed's SparseTextEmbedding (BM25/SPLADE), runs locally
│   │   │   │     on CPU, no API key, used for both indexing and query-time sparse vector
│   │   │   │
│   │   │   ├── hybrid_search.py
│   │   │   │     STAGE 4 — run dense search + sparse search against Qdrant in parallel,
│   │   │   │     fuse ranked lists via Reciprocal Rank Fusion (RRF), return top-N fused
│   │   │   │
│   │   │   └── rerank.py
│   │   │         STAGE 4 — send RRF top-N child chunks to Cohere rerank-english-v3.0,
│   │   │         return top-K reranked, then resolve each child → its parent_id →
│   │   │         fetch full parent text for LLM context
│   │   │
│   │   └── generation/
│   │       └── llm_groq.py
│   │             STAGE 5 — build prompt (system + parent contexts + citations format
│   │             instruction), call Groq chat completion (stream=True),
│   │             yield tokens, attach SourceChunk list to final response
│   │
│   ├── requirements.txt
│   └── Dockerfile
│         STAGE 6 — containerize backend for Render/Fly.io deployment
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx
│   │   │     STAGE 5 — landing page: app name, 3-4 feature bullets, "Upload Document" CTA
│   │   │
│   │   ├── chat/page.tsx
│   │   │     STAGE 5 — main chat interface, holds upload + chat state together
│   │   │
│   │   ├── components/
│   │   │   ├── UploadForm.tsx
│   │   │   │     STAGE 5 — drag/drop or file picker, calls POST /upload, shows progress
│   │   │   │
│   │   │   ├── ChatWindow.tsx
│   │   │   │     STAGE 5 — message list container, handles streaming token append
│   │   │   │
│   │   │   ├── MessageBubble.tsx
│   │   │   │     STAGE 5 — visually distinct user (right-aligned) vs AI (left-aligned) bubbles
│   │   │   │
│   │   │   └── SourcesPanel.tsx
│   │   │         STAGE 5 — "View Sources" expandable panel: chunk text snippet,
│   │   │         page number, link to signed Supabase URL for original file
│   │   │
│   │   └── lib/api.ts
│   │         STAGE 5 — typed fetch wrappers: uploadDocument(), sendChatMessage() (SSE reader)
│   │
│   ├── package.json
│   └── next.config.js
│
└── README.md
      STAGE 6 (REQUIRED DELIVERABLE) — tech stack list + explanation of how
      chunking (parent-child) and retrieval (hybrid RRF + rerank) work
```

## Per-chunk metadata schema (Qdrant point payload)

```json
{
  "chunk_id": "uuid",
  "doc_id": "uuid",
  "parent_id": "uuid | null",
  "chunk_type": "parent | child",
  "source_filename": "report.pdf",
  "page_number": 3,
  "chunk_index": 12,
  "chunk_text": "...",
  "char_start": 4210,
  "char_end": 4980,
  "created_at": "2026-07-06T12:00:00Z"
}
```
