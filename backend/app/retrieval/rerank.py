"""
Reranking + parent resolution — final stage of the retrieval pipeline.

Takes the RRF-fused candidate list (top 10), reranks using Cohere's
cross-encoder rerank model, selects the top 5, then resolves each
child → parent_id → full parent text for LLM context.

Retrieval funnel (final leg):
  RRF output:  TOP_K_AFTER_FUSION=10 candidates
  ────────────────────────────────────────
  Rerank:      TOP_K_AFTER_RERANK=5 → LLM
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import cohere

from app.config import settings
from app.retrieval.hybrid_search import RetrievedChunk
from app.storage.qdrant_client import get_parents_by_ids
from app.utils.cohere_manager import execute_with_rotation

logger = logging.getLogger(__name__)


# ── Result data class ──────────────────────────────────────────


@dataclass
class RetrievalResult:
    """
    Complete output of the retrieval pipeline.

    Contains everything the generation stage needs:
      • reranked children  — for citation metadata (page numbers, filenames, etc.)
      • parent contexts    — the actual text blocks sent to the LLM
      • parent_map         — parent_id → full parent payload (for lookup)
    """

    children: list[RetrievedChunk]
    parent_contexts: list[str]         # ordered parent texts for the LLM prompt
    parent_map: dict[str, dict]        # parent_id → full payload
    query: str                         # original query (for logging/debugging)

    @property
    def context_for_llm(self) -> str:
        """
        Format parent contexts as a numbered list for the LLM prompt.

        Each context block is labelled with its source filename and
        page number so the LLM can cite them in its answer.
        """
        blocks: list[str] = []
        seen_parents: set[str] = set()

        for i, child in enumerate(self.children, 1):
            pid = child.parent_id
            if pid and pid not in seen_parents and pid in self.parent_map:
                seen_parents.add(pid)
                parent = self.parent_map[pid]
                source = parent.get("source_filename", "unknown")
                page = parent.get("page_number", "?")
                text = parent.get("chunk_text", "")

                blocks.append(
                    f"[Context {len(blocks) + 1} | Source: {source}, Page: {page}]\n{text}"
                )

        return "\n\n---\n\n".join(blocks)


# ── Public API ─────────────────────────────────────────────────


def rerank_and_resolve(
    query: str,
    candidates: list[RetrievedChunk],
    top_k: int | None = None,
) -> RetrievalResult:
    """
    Rerank candidates with Cohere cross-encoder and resolve parents.

    Parameters
    ----------
    query      : the original user query
    candidates : RRF-fused chunks (typically 10)
    top_k      : how many to keep after reranking (default from settings)

    Returns
    -------
    RetrievalResult with reranked children, parent contexts, and
    full metadata on every chunk.
    """
    top_k = top_k or settings.top_k_after_rerank

    if not candidates:
        logger.warning("No candidates to rerank.")
        return RetrievalResult(
            children=[], parent_contexts=[], parent_map={}, query=query,
        )

    # ── Step 1: Cohere rerank ──────────────────────────────────
    documents = [c.chunk_text for c in candidates]

    logger.info(
        "Reranking %d candidates with %s (top_k=%d)...",
        len(candidates), settings.cohere_rerank_model, top_k,
    )

    def _do_rerank(client: cohere.Client):
        return client.rerank(
            query=query,
            documents=documents,
            model=settings.cohere_rerank_model,
            top_n=top_k,
        )

    rerank_response = execute_with_rotation(_do_rerank)

    # ── Step 2: Select top-K reranked children ─────────────────
    reranked_children: list[RetrievedChunk] = []
    for result in rerank_response.results:
        idx = result.index
        child = candidates[idx]
        child.score = result.relevance_score  # replace RRF score with rerank score
        reranked_children.append(child)

    logger.info(
        "Reranking complete: %d → %d candidates (scores: %s)",
        len(candidates),
        len(reranked_children),
        [f"{c.score:.4f}" for c in reranked_children],
    )

    # ── Step 3: Resolve child → parent text ────────────────────
    parent_ids = [
        c.parent_id for c in reranked_children
        if c.parent_id is not None
    ]

    parent_map: dict[str, dict] = {}
    parent_contexts: list[str] = []

    if parent_ids:
        parent_map = get_parents_by_ids(parent_ids)
        logger.info("Resolved %d unique parents.", len(parent_map))

        # Build ordered parent context list (deduplicated, in child rank order)
        seen_parents: set[str] = set()
        for child in reranked_children:
            pid = child.parent_id
            if pid and pid in parent_map and pid not in seen_parents:
                seen_parents.add(pid)
                parent_contexts.append(parent_map[pid].get("chunk_text", ""))

    return RetrievalResult(
        children=reranked_children,
        parent_contexts=parent_contexts,
        parent_map=parent_map,
        query=query,
    )


# ── Convenience: full retrieval pipeline in one call ───────────


def retrieve(
    query: str,
    doc_ids: list[str] | None = None,
) -> RetrievalResult:
    """
    Run the complete retrieval pipeline:
      1. Hybrid search (dense ∥ sparse → RRF)
      2. Rerank (Cohere cross-encoder)
      3. Parent resolution

    This is the single entry point the chat router should call.

    Parameters
    ----------
    query  : user's question
    doc_ids: optional document scope (list of IDs)

    Returns
    -------
    RetrievalResult ready for LLM generation.
    """
    from app.retrieval.hybrid_search import hybrid_search

    # Step 1: Hybrid search → 10 RRF-fused candidates
    candidates = hybrid_search(query=query, doc_ids=doc_ids)

    # Step 2+3: Rerank → 5 final + resolve parents
    result = rerank_and_resolve(query=query, candidates=candidates)

    logger.info(
        "Full retrieval complete: %d children, %d parent contexts",
        len(result.children), len(result.parent_contexts),
    )

    return result
