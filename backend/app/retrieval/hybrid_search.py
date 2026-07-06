"""
Hybrid search — dense + sparse retrieval with Reciprocal Rank Fusion.

Runs dense (Cohere) and sparse (BM25/fastembed) searches against
Qdrant in parallel via ThreadPoolExecutor, then fuses the two
ranked lists using RRF.

Retrieval funnel (configurable via .env):
  Dense:  TOP_K_DENSE=10 candidates
  Sparse: TOP_K_SPARSE=10 candidates
  ──────────────────────────────────
  Pool:   up to 20 unique children
  ──────────────────────────────────
  RRF:    TOP_K_AFTER_FUSION=10 → sent to reranker
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
    NamedSparseVector,
    SparseVector as QdrantSparseVector,
)

from app.config import settings
from app.embeddings.cohere_embed import embed_query
from app.retrieval.sparse import embed_sparse_query
from app.storage.qdrant_client import get_client

logger = logging.getLogger(__name__)


# ── Result data class ──────────────────────────────────────────


@dataclass
class RetrievedChunk:
    """
    A single chunk returned by the retrieval pipeline.
    Carries the full Qdrant payload so all metadata is available
    downstream without additional lookups.
    """

    chunk_id: str
    doc_id: str
    parent_id: str | None
    chunk_type: str
    source_filename: str
    page_number: int
    chunk_index: int
    chunk_text: str
    char_start: int
    char_end: int
    created_at: str
    score: float = 0.0  # RRF fused score (or raw Qdrant score before fusion)

    @classmethod
    def from_qdrant_hit(cls, hit, score_override: float | None = None) -> "RetrievedChunk":
        """Construct from a Qdrant ScoredPoint."""
        p = hit.payload
        return cls(
            chunk_id=p["chunk_id"],
            doc_id=p["doc_id"],
            parent_id=p.get("parent_id"),
            chunk_type=p["chunk_type"],
            source_filename=p["source_filename"],
            page_number=p["page_number"],
            chunk_index=p["chunk_index"],
            chunk_text=p["chunk_text"],
            char_start=p["char_start"],
            char_end=p["char_end"],
            created_at=p["created_at"],
            score=score_override if score_override is not None else hit.score,
        )


# ── Qdrant search helpers ─────────────────────────────────────


def _build_filter(doc_id: str | None) -> Filter | None:
    """
    Build a Qdrant filter that:
      1. Only returns child chunks (parents have zero vectors)
      2. Optionally scopes to a specific document
    """
    conditions = [
        FieldCondition(key="chunk_type", match=MatchValue(value="child")),
    ]
    if doc_id:
        conditions.append(
            FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
        )
    return Filter(must=conditions)


def _dense_search(
    dense_vector: list[float],
    doc_id: str | None,
    top_k: int,
) -> list[RetrievedChunk]:
    """Run cosine similarity search using the dense (Cohere) vector."""
    client = get_client()
    hits = client.search(
        collection_name=settings.qdrant_collection_name,
        query_vector=(settings.qdrant_dense_vector_name, dense_vector),
        query_filter=_build_filter(doc_id),
        limit=top_k,
        with_payload=True,
    )
    return [RetrievedChunk.from_qdrant_hit(h) for h in hits]


def _sparse_search(
    sparse_indices: list[int],
    sparse_values: list[float],
    doc_id: str | None,
    top_k: int,
) -> list[RetrievedChunk]:
    """Run BM25-style search using the sparse (fastembed) vector."""
    client = get_client()
    hits = client.search(
        collection_name=settings.qdrant_collection_name,
        query_vector=NamedSparseVector(
            name=settings.qdrant_sparse_vector_name,
            vector=QdrantSparseVector(
                indices=sparse_indices,
                values=sparse_values,
            ),
        ),
        query_filter=_build_filter(doc_id),
        limit=top_k,
        with_payload=True,
    )
    return [RetrievedChunk.from_qdrant_hit(h) for h in hits]


# ── Reciprocal Rank Fusion ─────────────────────────────────────


def _reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievedChunk]],
    k: int = 60,
    top_n: int = 10,
) -> list[RetrievedChunk]:
    """
    Fuse multiple ranked lists using Reciprocal Rank Fusion.

    For each chunk appearing in any list:
      score(chunk) = Σ  1 / (k + rank)
    where rank is the 1-indexed position in each list.

    Parameters
    ----------
    ranked_lists : list of ranked result lists
    k            : RRF constant (default 60, per literature)
    top_n        : number of results to return after fusion

    Returns
    -------
    Fused list sorted by RRF score, descending.
    """
    # chunk_id → (accumulated RRF score, best RetrievedChunk object)
    scores: dict[str, float] = {}
    best_chunk: dict[str, RetrievedChunk] = {}

    for ranked_list in ranked_lists:
        for rank_0, chunk in enumerate(ranked_list):
            rank_1 = rank_0 + 1  # 1-indexed
            rrf_contribution = 1.0 / (k + rank_1)

            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + rrf_contribution

            # Keep the chunk object (prefer the one with higher original score)
            if chunk.chunk_id not in best_chunk or chunk.score > best_chunk[chunk.chunk_id].score:
                best_chunk[chunk.chunk_id] = chunk

    # Sort by fused score descending
    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    results: list[RetrievedChunk] = []
    for cid in sorted_ids[:top_n]:
        chunk = best_chunk[cid]
        chunk.score = scores[cid]  # replace raw score with RRF score
        results.append(chunk)

    return results


# ── Public API ─────────────────────────────────────────────────


def hybrid_search(
    query: str,
    doc_id: str | None = None,
    top_k_dense: int | None = None,
    top_k_sparse: int | None = None,
    top_k_fused: int | None = None,
    rrf_k: int | None = None,
) -> list[RetrievedChunk]:
    """
    Run hybrid (dense + sparse) search with RRF fusion.

    1. Embed query → dense vector (Cohere, input_type=search_query)
    2. Embed query → sparse vector (fastembed BM25)
       ↳ Steps 1 & 2 run in parallel to minimise latency
    3. Search Qdrant with both vectors (also parallel)
    4. Fuse results via RRF
    5. Return top_k_fused candidates

    Parameters
    ----------
    query       : user's natural language question
    doc_id      : optional doc_id to scope search to one document
    top_k_dense : dense candidates (default from settings)
    top_k_sparse: sparse candidates (default from settings)
    top_k_fused : results after RRF (default from settings)
    rrf_k       : RRF constant (default from settings)

    Returns
    -------
    List of RetrievedChunk sorted by RRF score, descending.
    All metadata fields are populated.
    """
    top_k_dense = top_k_dense or settings.top_k_dense
    top_k_sparse = top_k_sparse or settings.top_k_sparse
    top_k_fused = top_k_fused or settings.top_k_after_fusion
    rrf_k = rrf_k or settings.rrf_k_constant

    logger.info(
        "Hybrid search: query='%s', doc_id=%s, dense_k=%d, sparse_k=%d, fused_k=%d",
        query[:80], doc_id, top_k_dense, top_k_sparse, top_k_fused,
    )

    # ── Step 1+2: Embed query (dense + sparse) in parallel ─────
    dense_vector: list[float] = []
    sparse_result = None

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_dense = executor.submit(embed_query, query)
        future_sparse = executor.submit(embed_sparse_query, query)

        dense_vector = future_dense.result()
        sparse_result = future_sparse.result()

    logger.info("Query embeddings generated (dense=%d dims, sparse=%d nonzero)",
                len(dense_vector), len(sparse_result.indices))

    # ── Step 3: Search Qdrant (dense + sparse) in parallel ─────
    dense_hits: list[RetrievedChunk] = []
    sparse_hits: list[RetrievedChunk] = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_d = executor.submit(
            _dense_search, dense_vector, doc_id, top_k_dense,
        )
        future_s = executor.submit(
            _sparse_search, sparse_result.indices, sparse_result.values,
            doc_id, top_k_sparse,
        )

        dense_hits = future_d.result()
        sparse_hits = future_s.result()

    logger.info("Search results: %d dense hits, %d sparse hits",
                len(dense_hits), len(sparse_hits))

    # ── Step 4: RRF fusion ─────────────────────────────────────
    fused = _reciprocal_rank_fusion(
        ranked_lists=[dense_hits, sparse_hits],
        k=rrf_k,
        top_n=top_k_fused,
    )

    logger.info("RRF fusion: %d candidates after fusion", len(fused))
    return fused
