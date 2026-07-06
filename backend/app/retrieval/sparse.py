"""
Sparse vector generation via fastembed.

Uses fastembed's SparseTextEmbedding with the Qdrant/bm25 model to
produce BM25-style sparse vectors.  Runs entirely on CPU — no API
key, no GPU required.

Used at both index time (Stage 3) and query time (Stage 4).
The same model instance is reused via module-level singleton for
performance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastembed import SparseTextEmbedding

from app.config import settings

logger = logging.getLogger(__name__)

# ── Sparse vector output ───────────────────────────────────────


@dataclass
class SparseVector:
    """Matches Qdrant's sparse vector format: parallel lists of indices and values."""
    indices: list[int]
    values: list[float]


# ── Module-level model singleton ───────────────────────────────

_model: SparseTextEmbedding | None = None


def _get_model() -> SparseTextEmbedding:
    """Lazy-load the sparse embedding model (first call takes a few seconds)."""
    global _model
    if _model is None:
        logger.info("Loading sparse embedding model (Qdrant/bm25)...")
        _model = SparseTextEmbedding(model_name="Qdrant/bm25")
        logger.info("Sparse embedding model loaded.")
    return _model


# ── Public API ─────────────────────────────────────────────────


def embed_sparse(texts: list[str]) -> list[SparseVector]:
    """
    Generate sparse (BM25-style) vectors for a list of texts.

    Parameters
    ----------
    texts : list of strings to embed

    Returns
    -------
    List of SparseVector, one per input text.  Each contains
    parallel lists of token indices and their BM25 weights.
    """
    if not texts:
        return []

    model = _get_model()

    logger.info("Generating sparse vectors for %d texts...", len(texts))

    results: list[SparseVector] = []
    for embedding in model.embed(texts, batch_size=64):
        results.append(
            SparseVector(
                indices=embedding.indices.tolist(),
                values=embedding.values.tolist(),
            )
        )

    if len(results) != len(texts):
        raise RuntimeError(
            f"Sparse embedding count mismatch: got {len(results)} "
            f"vectors for {len(texts)} texts"
        )

    logger.info("Sparse vector generation complete.")
    return results


def embed_sparse_query(query: str) -> SparseVector:
    """
    Generate a sparse vector for a single search query.

    Convenience wrapper around embed_sparse.
    """
    vectors = embed_sparse([query])
    return vectors[0]
