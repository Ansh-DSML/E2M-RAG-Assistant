"""
Qdrant vector store client.

Manages the rag_chunks collection with named vectors:
  • "dense"  — 1024-dim Cohere embed-english-v3.0, cosine distance
  • "sparse" — BM25/SPLADE-style via fastembed

Both parent and child chunks are stored in the same collection.
Children carry both vector types; parents are stored as payload-only
points (no vectors) for text lookup at generation time.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    SparseVectorParams,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType,
)

from app.config import settings
from app.chunking.parent_child import ChunkRecord
from app.retrieval.sparse import SparseVector

logger = logging.getLogger(__name__)

# ── Client singleton ───────────────────────────────────────────

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    """Return a reusable Qdrant client instance."""
    global _client
    if _client is None:
        _client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=30,
        )
    return _client


# ── Collection management ──────────────────────────────────────


def ensure_collection() -> None:
    """
    Create the rag_chunks collection if it doesn't exist yet.

    Uses the exact schema from SETUP_DEPLOYMENT.md:
      dense  → 1024-dim cosine (Cohere embed-english-v3.0)
      sparse → SparseVectorParams (BM25/SPLADE)
    """
    client = get_client()
    collection_name = settings.qdrant_collection_name

    # Check if collection already exists
    collections = client.get_collections().collections
    existing_names = {c.name for c in collections}

    if collection_name in existing_names:
        logger.info("Collection '%s' already exists.", collection_name)
        return

    logger.info("Creating collection '%s'...", collection_name)
    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            settings.qdrant_dense_vector_name: VectorParams(
                size=1024,
                distance=Distance.COSINE,
            ),
        },
        sparse_vectors_config={
            settings.qdrant_sparse_vector_name: SparseVectorParams(),
        },
    )
    logger.info("Collection '%s' created successfully.", collection_name)
    _create_payload_indexes(collection_name)


def recreate_collection() -> None:
    """
    Delete and recreate the collection from scratch.

    Useful during development or when the schema changes.
    """
    client = get_client()
    collection_name = settings.qdrant_collection_name

    # Delete if exists
    collections = client.get_collections().collections
    existing_names = {c.name for c in collections}

    if collection_name in existing_names:
        logger.info("Deleting existing collection '%s'...", collection_name)
        client.delete_collection(collection_name=collection_name)
        logger.info("Collection '%s' deleted.", collection_name)

    # Create fresh
    ensure_collection()


def _create_payload_indexes(collection_name: str) -> None:
    """
    Create payload indexes required for filtered search.

    Qdrant Cloud requires explicit keyword indexes on fields
    used in query filters; without them, filtered searches
    return 400 Bad Request.
    """
    client = get_client()

    for field_name in ("chunk_type", "doc_id"):
        logger.info("Creating payload index: %s (keyword)", field_name)
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field_name,
            field_schema=PayloadSchemaType.KEYWORD,
        )

    logger.info("Payload indexes created.")


# ── Upsert operations ─────────────────────────────────────────

# Qdrant recommends batches of ~100 points for upserts
_UPSERT_BATCH_SIZE = 100


def upsert_child_chunks(
    children: list[ChunkRecord],
    dense_vectors: list[list[float]],
    sparse_vectors: list[SparseVector],
) -> int:
    """
    Upsert child chunks into Qdrant with both dense and sparse vectors.

    Parameters
    ----------
    children       : child ChunkRecords (from parent_child.build_chunks)
    dense_vectors  : 1024-dim Cohere embeddings, aligned with children
    sparse_vectors : BM25 sparse vectors, aligned with children

    Returns
    -------
    Number of points upserted.
    """
    if not children:
        return 0

    if len(children) != len(dense_vectors) or len(children) != len(sparse_vectors):
        raise ValueError(
            f"Length mismatch: {len(children)} children, "
            f"{len(dense_vectors)} dense vectors, "
            f"{len(sparse_vectors)} sparse vectors"
        )

    client = get_client()
    collection_name = settings.qdrant_collection_name

    points: list[PointStruct] = []
    for child, dense_vec, sparse_vec in zip(children, dense_vectors, sparse_vectors):
        point = PointStruct(
            id=child.chunk_id,
            vector={
                settings.qdrant_dense_vector_name: dense_vec,
                settings.qdrant_sparse_vector_name: {
                    "indices": sparse_vec.indices,
                    "values": sparse_vec.values,
                },
            },
            payload=child.to_payload(),
        )
        points.append(point)

    # Batch upsert
    total_upserted = 0
    for batch_start in range(0, len(points), _UPSERT_BATCH_SIZE):
        batch = points[batch_start : batch_start + _UPSERT_BATCH_SIZE]

        logger.info(
            "Upserting child batch %d–%d of %d points...",
            batch_start,
            batch_start + len(batch) - 1,
            len(points),
        )

        client.upsert(
            collection_name=collection_name,
            points=batch,
        )
        total_upserted += len(batch)

    logger.info("Upserted %d child points total.", total_upserted)
    return total_upserted


def upsert_parent_chunks(parents: list[ChunkRecord]) -> int:
    """
    Upsert parent chunks into Qdrant (payload only, no vectors).

    Parents are stored for text lookup at generation time:
    when a child is retrieved, we resolve child.parent_id → parent
    to get the full context block for the LLM.

    We store parents with a zero dense vector and empty sparse vector
    since Qdrant requires vectors for points in a vectored collection.
    They are never returned by similarity search because their zero
    vectors have no meaningful similarity to any query.
    """
    if not parents:
        return 0

    client = get_client()
    collection_name = settings.qdrant_collection_name

    # Zero vector for parents (1024 dims to match collection schema)
    zero_dense = [0.0] * 1024

    points: list[PointStruct] = []
    for parent in parents:
        point = PointStruct(
            id=parent.chunk_id,
            vector={
                settings.qdrant_dense_vector_name: zero_dense,
                settings.qdrant_sparse_vector_name: {
                    "indices": [],
                    "values": [],
                },
            },
            payload=parent.to_payload(),
        )
        points.append(point)

    # Batch upsert
    total_upserted = 0
    for batch_start in range(0, len(points), _UPSERT_BATCH_SIZE):
        batch = points[batch_start : batch_start + _UPSERT_BATCH_SIZE]

        logger.info(
            "Upserting parent batch %d–%d of %d points...",
            batch_start,
            batch_start + len(batch) - 1,
            len(points),
        )

        client.upsert(
            collection_name=collection_name,
            points=batch,
        )
        total_upserted += len(batch)

    logger.info("Upserted %d parent points total.", total_upserted)
    return total_upserted


# ── Query helpers (used by retrieval in Stage 4) ───────────────


def get_parent_by_id(parent_id: str) -> dict | None:
    """
    Fetch a single parent chunk's payload by its chunk_id.

    Used during generation to resolve child → parent context.
    """
    client = get_client()
    collection_name = settings.qdrant_collection_name

    results = client.retrieve(
        collection_name=collection_name,
        ids=[parent_id],
    )

    if not results:
        return None

    return results[0].payload


def get_parents_by_ids(parent_ids: list[str]) -> dict[str, dict]:
    """
    Batch-fetch multiple parent chunks by their chunk_ids.

    Returns a dict mapping parent_id → payload.
    """
    if not parent_ids:
        return {}

    client = get_client()
    collection_name = settings.qdrant_collection_name

    # Deduplicate
    unique_ids = list(set(parent_ids))

    results = client.retrieve(
        collection_name=collection_name,
        ids=unique_ids,
    )

    return {r.id: r.payload for r in results}


def get_collection_info() -> dict:
    """Return collection stats (point count, vector counts, etc.)."""
    client = get_client()
    info = client.get_collection(settings.qdrant_collection_name)
    return {
        "collection_name": settings.qdrant_collection_name,
        "points_count": info.points_count,
        "vectors_count": info.vectors_count,
        "status": info.status.value if info.status else "unknown",
    }
