# E2M RAG Assistant

A full-stack, document-based AI assistant built for the E2M AI Engineering Assessment. This application allows users to upload multiple PDF or DOCX files and interactively ask questions about their content. The system uses a modern Retrieval-Augmented Generation (RAG) pipeline to ensure all answers are firmly grounded in the uploaded documents, complete with source citations.

## 🚀 Live Demo
- **Frontend (Vercel)**: https://e2-m-rag-assistant-weld.vercel.app/
- **Backend (Render)**: https://e2m-rag-assistant.onrender.com

## 🛠️ Tech Stack

**Frontend**
- **Framework**: Next.js 14 (App Router) / React
- **Styling**: Vanilla CSS (Custom High-Contrast B&W Theme)
- **Data Visualization**: Recharts (for background LLM metrics)

**Backend**
- **Framework**: FastAPI (Python)
- **Document Parsing**: PyMuPDF (`fitz`) for precise PDF text extraction, `python-docx` for Word documents.
- **LLM Generation**: Groq (Llama-3.3-70b-versatile) for lightning-fast inference.
- **Embeddings**: Cohere (`embed-english-v3.0`).
- **Vector Database**: Qdrant (Cloud).
- **Blob Storage**: Supabase Storage (for securely hosting uploaded raw documents).
- **Evaluation/Metrics**: LangSmith + LLM-as-a-judge for background scoring.

## 🧠 How Chunking and Retrieval Works

This application implements an **advanced "Expert-Then-Fuse" RAG architecture**, prioritizing high recall and highly accurate semantic context.

### 1. Document Processing & Chunking
When a document is uploaded:
1. **Extraction**: Text is extracted page-by-page (PDF) or paragraph-by-paragraph (DOCX).
2. **Parent-Child Chunking**: We use a hierarchical chunking strategy.
   - **Parent Chunks (1200 tokens)**: Large chunks of text that provide broad context.
   - **Child Chunks (300 tokens, 50 token overlap)**: Smaller, overlapping sub-chunks generated from the parents. 
3. **Embedding**: Only the *Child Chunks* are embedded using Cohere's V3 embeddings. This allows for highly precise semantic matching (since smaller text chunks have denser, more specific semantic meaning).
4. **Storage**: Both parent and child chunks are stored in Qdrant.

### 2. The Retrieval Pipeline
When a user asks a question, the backend executes a multi-stage retrieval process:
1. **Hybrid Search**: We query Qdrant using both Dense Vectors (semantic meaning via Cohere) and Sparse Vectors (keyword matching via BM25/SPLADE equivalents).
2. **Reciprocal Rank Fusion (RRF)**: The results from the dense and sparse searches are mathematically fused together to ensure both keyword matches and semantic matches rise to the top.
3. **Parent Context Retrieval**: For the top matching *Child Chunks*, the system automatically replaces them with their corresponding *Parent Chunks*. This ensures the LLM receives the full, broader context surrounding the exact semantic match, drastically reducing hallucinations and "lost in the middle" phenomena.
4. **Cross-Encoder Reranking**: The retrieved parent chunks are passed through a Cohere Reranker model to score and re-order them based on their direct relevance to the user's specific query.
5. **Generation**: The absolute top chunks are injected into the Llama 3 prompt, and the response is streamed back to the frontend alongside the source citations.

### 3. Background Evaluation (LLM-as-a-Judge)
After every response, a background thread calculates reference-free metrics using LangSmith and an impartial LLM judge. It calculates:
- **Time to First Token (TTFT) & Total Latency**
- **Faithfulness**: Did the model hallucinate outside the provided chunks?
- **Answer Relevancy**: Did the model directly answer the user's question?
- **Context Relevance**: Was the retrieved context actually useful?

These metrics can be viewed in the "View Metrics" dashboard in the frontend.

## 💻 Local Setup

1. **Clone the repository**
2. **Backend**:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # or .\.venv\Scripts\activate on Windows
   pip install -r ../requirements.txt
   ```
   *Note: Ensure you copy the `.env` file into the root directory with your API keys.*
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
3. **Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
