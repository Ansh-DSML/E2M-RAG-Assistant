# DocuMind

A full stack, document based AI assistant built for the E2M AI Engineering Assessment. This application allows users to upload multiple PDF or DOCX files and interactively ask questions about their content. The system uses a modern Retrieval Augmented Generation architecture to ensure all answers are firmly grounded in the uploaded documents, complete with source citations.

## Live Demo
* Frontend: <a href="https://e2%2Dm%2Drag%2Dassistant%2Dweld.vercel.app/">Vercel Deployment</a>
* Backend: <a href="https://e2m%2Drag%2Dassistant.onrender.com">Render Deployment</a>
* Important Notice for Reviewers: The backend is deployed on Render free tier. If the application has not been used recently, the server will go to sleep. Please allow up to 60 seconds for the backend to wake up upon your first document upload or interaction. If it does not start after a minute, please simply refresh the page.

## DELIVERABLE: Tech Stack

### Frontend
* Framework: Next.js 14 and React
* Styling: Vanilla CSS with a Custom High Contrast Theme
* Data Visualization: Recharts for background LLM metrics

### Backend
* Framework: FastAPI and Python
* Document Parsing: PyMuPDF for precise PDF text extraction, python docx for Word documents
* LLM Generation: Groq Llama 3.3 70b versatile for lightning fast inference
* Embeddings: Cohere embed english v3.0 API
* Vector Database: Qdrant Cloud
* Blob Storage: Supabase Storage for securely hosting uploaded raw documents
* Evaluation and Metrics: LangSmith and an impartial LLM judge for background scoring

## DELIVERABLE: How Chunking and Retrieval Works

This application implements an advanced RAG architecture, prioritizing high recall and highly accurate semantic context.

### 1. Document Processing and Chunking
When a document is uploaded:
* Extraction: Text is extracted page by page for PDFs or paragraph by paragraph for DOCX.
* Hierarchical Chunking: We use a parent and child chunking strategy.
* Parent Chunks: Large chunks of 1200 tokens that provide broad context.
* Child Chunks: Smaller, overlapping sub chunks of 300 tokens generated from the parents, maintaining a 50 token overlap to preserve contextual continuity.
* Embedding: Only the Child Chunks are embedded using Cohere V3 embeddings. This allows for highly precise semantic matching since smaller text chunks have denser, more specific semantic meaning.
* Storage: Both parent and child chunks are stored in Qdrant.

### 2. The Retrieval Pipeline
When a user asks a question, the backend executes a multi stage retrieval process:
* Hybrid Search: We query Qdrant using both Dense Vectors for semantic meaning via Cohere and Sparse Vectors for keyword matching via BM25.
* Reciprocal Rank Fusion: The results from the dense and sparse searches are mathematically combined together to ensure both BM25 keyword matches and semantic matches rise to the top.
* Parent Context Retrieval: For the top matching Child Chunks, the system automatically replaces them with their corresponding Parent Chunks. This ensures the LLM receives the full, broader context surrounding the exact semantic match, drastically reducing hallucinations and lost in the middle phenomena.
* Cross Encoder Reranking: The retrieved parent chunks are passed through a Cohere Reranker model to score and reorder them based on their direct relevance to the user's specific query.
* Generation: The absolute top chunks are injected into the Llama 3 prompt, and the response is streamed back to the frontend alongside the source citations.

## Architectural Justifications

* Embeddings via API vs Local Deployment: We explicitly chose to use the Cohere API for embeddings rather than loading a local open source model directly on the backend. This is because deploying on free tier cloud providers like Render imposes severe RAM limits usually around 512MB and lacks GPU acceleration. Loading a quality dense embedding model locally would instantly trigger an Out Of Memory crash and drastically increase cold start times. Delegating embeddings to Cohere ensures the backend remains exceptionally lightweight and blazing fast.

## System Design and Add On Features

* Mobile Optimization: The entire chat interface and landing page feature dedicated responsive media queries, ensuring buttons, headers, and text naturally stack and scale for mobile users without compromising the desktop experience.
* Real Time Metrics Dashboard: An automated background evaluation thread uses an LLM judge to grade every response for Faithfulness, Answer Relevancy, and Context Relevance.
* Token Stream Optimization: The backend streams the LLM response chunk by chunk to the frontend via Server Sent Events, providing a perceived Time To First Token of under 1.5 seconds.
* Key Rotation: Built in support for API key rotation to seamlessly handle rate limits.

## Future Scope

* Distributed Caching: Implementing Redis to cache frequently asked queries and their respective embedded context.
* Multi Modal Understanding: Upgrading the extraction pipeline to use OCR for parsing images and complex tables within PDFs.
* User Authentication: Adding OAuth to allow users to save their chat history securely across multiple sessions.

## Local Setup

1. Clone the repository
2. Backend:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r ../requirements.txt
   ```
   Note: Ensure you copy the `.env` file into the root directory with your API keys.
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
3. Frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
