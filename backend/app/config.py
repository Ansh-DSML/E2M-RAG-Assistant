"""
Central configuration — single source of truth for every env var.

Uses pydantic-settings so values are validated at startup; a missing
required key will crash the app immediately instead of failing silently
at runtime deep inside a request handler.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        # Look for .env two levels up (repo root) first, then backend/.env
        env_file=("../../.env", "../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",  # ignore vars we don't declare (e.g. PATH)
    )

    # ── Supabase (raw document storage) ──────────────────────────
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_bucket: str = "documents"
    supabase_docs_table: str = "documents_meta"

    # ── Qdrant Cloud (vector store) ──────────────────────────────
    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection_name: str = "rag_chunks"
    qdrant_dense_vector_name: str = "dense"
    qdrant_sparse_vector_name: str = "sparse"

    # ── Cohere (embeddings + rerank) ─────────────────────────────
    cohere_api_key: str
    cohere_embed_model: str = "embed-english-v3.0"
    cohere_embed_input_type_doc: str = "search_document"
    cohere_embed_input_type_query: str = "search_query"
    cohere_rerank_model: str = "rerank-english-v3.0"

    # ── Groq (LLM generation) ───────────────────────────────────
    groq_api_key: str
    groq_api_key_judge: str
    groq_model: str = "llama-3.3-70b-versatile"

    # ── Chunking config ─────────────────────────────────────────
    chunk_parent_tokens: int = 1200
    chunk_child_tokens: int = 300
    chunk_overlap_tokens: int = 50

    # ── Retrieval config ────────────────────────────────────────
    top_k_dense: int = 10
    top_k_sparse: int = 10
    rrf_k_constant: int = 60
    top_k_after_fusion: int = 10
    top_k_after_rerank: int = 5

    # ── App config ──────────────────────────────────────────────
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"
    max_upload_size_mb: int = 50
    allowed_extensions: str = "pdf,docx"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS_ORIGINS into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_extension_list(self) -> list[str]:
        """Parse comma-separated ALLOWED_EXTENSIONS into a list."""
        return [e.strip().lower() for e in self.allowed_extensions.split(",") if e.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


# Singleton — import this everywhere:  from app.config import settings
settings = Settings()
