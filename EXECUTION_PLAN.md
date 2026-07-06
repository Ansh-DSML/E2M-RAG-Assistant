# Execution Plan — Document-Based AI Assistant (23 hours remaining)

Tech stack locked: FastAPI · Supabase Storage · Qdrant Cloud · Cohere (embed + rerank) · fastembed (sparse/BM25) · Groq (LLM) · Next.js (React)

Rule for the whole build: **get one document flowing end-to-end (upload → answer with citation) before polishing anything.** A working ugly app beats a half-built pretty one.

---

## STAGE 0 — Repo & Accounts (Hour 1–2)

- [ ] Create GitHub repo, scaffold folders per PROJECT_STRUCTURE.md
- [ ] Create Supabase project → create Storage bucket `documents`
- [ ] Create Qdrant Cloud free cluster → note URL + API key
- [ ] Get Cohere trial API key (dashboard.cohere.com)
- [ ] Get Groq API key (console.groq.com)
- [ ] Fill `.env` from `.env.example`
- [ ] `pip install fastapi uvicorn python-multipart pydantic-settings supabase qdrant-client cohere groq fastembed pymupdf python-docx pandas`
- [ ] `npx create-next-app@latest frontend`
- [ ] Backend: `main.py` returns `{"status": "ok"}` on `/health`. Confirm it runs.
- [ ] Frontend: default Next.js page loads. Confirm it runs.

**Checkpoint:** both servers boot locally, backend responds to health check.

---

## STAGE 1 — Config & Schemas (Hour 2–3)

- [ ] `config.py`: pydantic Settings class, loads every `.env` var
- [ ] `schemas.py`: UploadResponse, ChatRequest, ChatResponse, SourceChunk
- [ ] Wire config into `main.py`, confirm no import errors

**Checkpoint:** `from app.config import settings` works anywhere in the app.

---

## STAGE 2 — Parsing + Upload + Raw Storage (Hour 3–7)

- [ ] `base.py`: ParsedDocument dataclass
- [ ] `pdf_parser.py`: page-by-page text extraction via pymupdf
- [ ] `docx_parser.py`: paragraph extraction via python-docx
- [ ] `csv_parser.py`: row-group extraction via pandas
- [ ] `json_parser.py`: key/record flattening
- [ ] `dispatcher.py`: route by file extension
- [ ] `supabase_client.py`: `upload_raw_file()`, `get_signed_url()`
- [ ] `upload.py` router: accept file → validate → save to Supabase → parse → return doc_id + parsed unit count (chunking comes next stage, so for now just prove parsing works)

**Checkpoint:** Upload a real PDF via `/docs` (FastAPI Swagger UI), confirm parsed text + page numbers print correctly, confirm file appears in Supabase Storage bucket.

---

## STAGE 3 — Chunking + Embedding + Vector Storage (Hour 7–11)

- [ ] `parent_child.py`: build parent chunks (~1200 tok) and nested child chunks (~300 tok, overlap ~50 tok), assign parent_id to each child
- [ ] `cohere_embed.py`: batch embed all child chunks (`input_type=search_document`)
- [ ] `sparse.py`: generate sparse vectors for all child chunks via fastembed (local, CPU)
- [ ] `qdrant_client.py`: create collection with named vectors (`dense`, `sparse`), upsert child chunks with full metadata payload (see PROJECT_STRUCTURE.md schema). Store parent chunks too (either same collection with `chunk_type: parent`, or a lightweight separate lookup — same collection is simpler)
- [ ] Update `upload.py` to call chunking → embedding → Qdrant upsert as one pipeline after parsing

**Checkpoint:** After upload, query Qdrant Cloud dashboard directly, confirm points exist with correct payload fields and both vector types populated.

---

## STAGE 4 — Retrieval Pipeline (Hour 11–15)

- [ ] `hybrid_search.py`: run dense search (Cohere query embed, `input_type=search_query`) and sparse search (fastembed) against Qdrant in parallel, fuse results with RRF (`score = sum(1 / (k + rank))` per document across both lists, k≈60)
- [ ] `rerank.py`: send RRF top-N child chunks' text to Cohere rerank, keep top-K (e.g. top 5)
- [ ] Resolve each reranked child → its parent_id → fetch parent chunk text (this is what actually goes to the LLM as context)
- [ ] Write a standalone test script that runs a query end-to-end and prints retrieved parent contexts + scores — test this BEFORE wiring to the LLM, so retrieval bugs are isolated

**Checkpoint:** Standalone script returns relevant parent context for a test query in well under a second (excluding rerank API latency, which you should measure separately).

---

## STAGE 5 — Generation + Chat Endpoint + Frontend (Hour 15–19)

- [ ] `llm_groq.py`: build prompt (system instructions + numbered parent contexts + explicit "cite page numbers" instruction), call Groq with `stream=True`
- [ ] `chat.py` router: POST /chat → run retrieval → run generation → stream tokens (SSE) → attach SourceChunk list (chunk_text snippet, page_number, source_filename, signed URL) at the end of the stream
- [ ] Frontend `UploadForm.tsx`: file picker, POST to `/upload`, show doc_id/status
- [ ] Frontend `ChatWindow.tsx` + `MessageBubble.tsx`: distinct user/AI styling, append streamed tokens live
- [ ] Frontend `SourcesPanel.tsx`: "View Sources" expandable list per AI message — chunk snippet, page number, clickable link to signed Supabase file URL
- [ ] Landing page `page.tsx`: app name, 3-4 feature bullets, CTA into chat/upload page

**Checkpoint:** Full manual flow works in browser — upload a PDF, ask a question, see streamed answer, click "View Sources," see chunk text + page number + working link to original file.

---

## STAGE 6 — Deploy, README, Buffer (Hour 19–23)

- [ ] Backend: Dockerfile, deploy to Render (free web service) or Fly.io — set all env vars in host dashboard
- [ ] Frontend: deploy to Vercel (free), set `NEXT_PUBLIC_API_URL` to deployed backend URL
- [ ] Update CORS_ORIGINS in backend config to include deployed frontend URL
- [ ] Test the full flow again on the deployed URLs, not just localhost
- [ ] Write `README.md`: tech stack table + chunking/retrieval explanation (required deliverable — see SETUP_DEPLOYMENT.md for structure)
- [ ] Reserve last ~1-2 hours purely as bug buffer — don't schedule new features here

---

## Cut list if you fall behind schedule

If you're behind by hour 15, cut in this order (stop cutting once you're back on pace):

1. Sparse/hybrid search + RRF → fall back to dense-only similarity search
2. Streaming responses → return full answer at once
3. Reranking → skip, use raw dense top-k directly
4. Parent-child chunking → fall back to flat chunking (still keep page_number metadata, citations still work)
5. Never cut: file upload, basic chat, and the "view sources with page number" citation — these three are explicitly named as required in the assessment brief.
