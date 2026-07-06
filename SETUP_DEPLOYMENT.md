# Setup & Deployment Guide

## Important: no GPU needed anywhere in this stack

Embeddings run through the **Cohere API** (remote), reranking runs through the **Cohere rerank API** (remote), and the LLM runs through **Groq** (remote). The only "local" compute is sparse vector generation for hybrid search via `fastembed`, which uses BM25/SPLADE-style scoring — this is CPU-only and fast even on a free-tier host. You do not need Lightning AI, Colab, or any GPU-backed deployment target. This simplifies hosting to any free CPU web service.

---

## Part 1 — Supabase Setup (raw document storage)

1. Go to [supabase.com](https://supabase.com) → New Project → pick a name/region → wait ~2 min for provisioning.
2. In the dashboard, go to **Storage** → **Create a new bucket** → name it `documents`. Set it to **private** (you'll serve files via signed URLs, not public links, since these may be user-uploaded sensitive docs).
3. Go to **Project Settings → API**. Copy:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` key → `SUPABASE_ANON_KEY`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY` (server-side only, never expose to frontend)
4. (Optional but recommended) Go to **Table Editor** → create a table `documents_meta` with columns: `doc_id (uuid, pk)`, `filename (text)`, `uploaded_at (timestamp)`, `chunk_count (int)`. This lets you list previously uploaded docs later if you have time.
5. In your backend, use the `supabase-py` client with the **service role key** so you can freely read/write the bucket without RLS friction during the assessment. (For a real product you'd tighten RLS policies — not needed for a 24h demo.)
6. To let the frontend view an original file for "View Sources," generate a **signed URL** server-side (`supabase.storage.from_("documents").create_signed_url(path, expires_in=3600)`) and return that URL in your chat response payload — don't expose the service role key or raw bucket access to the frontend.

---

## Part 2 — Qdrant Cloud Setup (vector store)

1. Go to [cloud.qdrant.io](https://cloud.qdrant.io) → sign up → **Create Cluster** → choose the free tier (1GB, sufficient for a document assessment demo).
2. Once provisioned, copy the **Cluster URL** → `QDRANT_URL`.
3. Go to **API Keys** → generate one → `QDRANT_API_KEY`.
4. Create your collection with **named vectors** so one point holds both a dense and a sparse vector:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, SparseVectorParams

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

client.create_collection(
    collection_name="rag_chunks",
    vectors_config={
        "dense": VectorParams(size=1024, distance=Distance.COSINE)  # 1024 = Cohere embed-english-v3.0 dim
    },
    sparse_vectors_config={
        "sparse": SparseVectorParams()
    },
)
```

5. Verify from the Qdrant Cloud dashboard's **Collections** tab that `rag_chunks` exists before moving on to upserting real data.

---

## Part 3 — Free Deployment (no GPU required)

### Backend (FastAPI)

Pick **one**:
- **Render** (render.com): New → Web Service → connect repo → set build command (`pip install -r requirements.txt`) and start command (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`) → add all `.env` vars under Environment tab. Free tier sleeps after inactivity — mention this in your README if the demo has a cold-start delay.
- **Fly.io** (fly.io): `fly launch` in the backend folder, follow prompts, `fly secrets set KEY=value` for each env var, `fly deploy`.

Either is fine — Render is simpler for a first deploy, Fly.io has less aggressive sleep behavior on free tier.

### Frontend (Next.js)

- **Vercel** (vercel.com): Import the repo, set root directory to `frontend/`, add `NEXT_PUBLIC_API_URL` env var pointing to your deployed backend URL, deploy. Vercel's free tier is effectively instant and doesn't sleep.

### After both are deployed

- Update `CORS_ORIGINS` in your backend's `.env`/host config to include your Vercel URL, redeploy backend.
- Test the full upload → chat → view sources flow against the **deployed** URLs before considering it done — local-only success doesn't guarantee deployed success (CORS, env var typos, and signed URL expiry are the most common gotchas).

---

## README.md structure (required deliverable per assessment brief)

Your final README should cover, briefly:

1. **Tech stack** — FastAPI, Supabase Storage, Qdrant Cloud, Cohere (embed + rerank), fastembed (sparse), Groq (LLM), Next.js.
2. **How chunking works** — parent-child strategy: parents (~1200 tokens) preserve broad context, children (~300 tokens, overlapping) are what gets embedded and searched for precision; when a child is retrieved, its parent's full text is what's actually sent to the LLM.
3. **How retrieval works** — hybrid search: dense (Cohere embeddings) + sparse (BM25-style via fastembed) run in parallel, fused via Reciprocal Rank Fusion, then reranked with Cohere's cross-encoder rerank model, top-K passed to the LLM alongside citation metadata (filename + page number).
4. Known limitations / things cut due to time (be upfront — assessors respect this more than silence).
