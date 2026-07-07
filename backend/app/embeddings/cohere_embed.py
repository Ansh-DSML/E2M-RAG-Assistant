"""
Cohere dense embedding client.

Handles batch embedding of text chunks via Cohere embed-english-v3.0.
Cohere's API accepts a maximum of 96 texts per call, so this module
automatically batches larger lists.

CRITICAL distinction enforced here:
  • Index time → input_type = "search_document"
  • Query time → input_type = "search_query"
  Mixing these up silently degrades retrieval quality.
"""

from __future__ import annotations

import logging
from typing import Literal

import cohere

from app.config import settings
from app.utils.cohere_manager import execute_with_rotation

logger = logging.getLogger(__name__)

# Cohere batch limit (embed-english-v3.0)
_MAX_BATCH_SIZE = 96


def embed_texts(
    texts: list[str],
    input_type: Literal["search_document", "search_query"] | None = None,
) -> list[list[float]]:
    """
    Embed a list of texts using Cohere embed-english-v3.0.

    Parameters
    ----------
    texts      : list of strings to embed
    input_type : "search_document" for indexing, "search_query" for retrieval.
                 Defaults to settings value for documents.

    Returns
    -------
    List of 1024-dimensional float vectors, one per input text.
    """
    if not texts:
        return []

    input_type = input_type or settings.cohere_embed_input_type_doc

    all_embeddings: list[list[float]] = []

    # Process in batches of _MAX_BATCH_SIZE
    for batch_start in range(0, len(texts), _MAX_BATCH_SIZE):
        batch = texts[batch_start : batch_start + _MAX_BATCH_SIZE]

        logger.info(
            "Embedding batch %d–%d of %d texts (input_type=%s)",
            batch_start,
            batch_start + len(batch) - 1,
            len(texts),
            input_type,
        )

        def _do_embed(client: cohere.Client, b: list[str]) -> list[list[float]]:
            response = client.embed(
                texts=b,
                model=settings.cohere_embed_model,
                input_type=input_type,
                embedding_types=["float"],
            )
            return response.embeddings.float

        batch_vectors = execute_with_rotation(_do_embed, batch)
        all_embeddings.extend(batch_vectors)

    if len(all_embeddings) != len(texts):
        raise RuntimeError(
            f"Embedding count mismatch: got {len(all_embeddings)} "
            f"vectors for {len(texts)} texts"
        )

    return all_embeddings


def embed_query(query: str) -> list[float]:
    """
    Embed a single search query.

    Convenience wrapper that forces input_type="search_query".
    """
    vectors = embed_texts(
        [query],
        input_type=settings.cohere_embed_input_type_query,
    )
    return vectors[0]
