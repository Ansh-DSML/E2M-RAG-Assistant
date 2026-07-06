"""
Groq LLM generation — streaming chat completions.

Builds a prompt with:
  - System instructions (role, citation format)
  - Numbered parent context blocks (with source filename + page)
  - User query

Streams tokens via Groq's stream=True for low-latency response.
"""

from __future__ import annotations

import logging
from typing import Generator

from groq import Groq

from app.config import settings

logger = logging.getLogger(__name__)

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


SYSTEM_PROMPT = """You are a helpful document assistant. You answer questions based ONLY on the provided context passages below. Follow these rules strictly:

1. Use ONLY the information from the provided context passages to answer.
2. If the context doesn't contain enough information to answer, say so clearly.
3. ALWAYS cite your sources using the format [Source: filename, Page: N] after each claim.
4. Be precise and thorough in your answers.
5. If multiple context passages are relevant, synthesize information from all of them.
6. Do not make up or hallucinate any information not present in the context."""


def _build_messages(
    query: str,
    context_for_llm: str,
) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Context passages:\n\n{context_for_llm}\n\n---\n\nQuestion: {query}\n\nProvide a comprehensive answer based on the context above. Remember to cite sources.""",
        },
    ]


def generate_stream(
    query: str,
    context_for_llm: str,
) -> Generator[str, None, None]:
    client = _get_client()
    messages = _build_messages(query, context_for_llm)

    logger.info("Starting Groq stream (model=%s)...", settings.groq_model)

    stream = client.chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        stream=True,
        temperature=0.1,
        max_tokens=2048,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content

    logger.info("Groq stream complete.")


def generate_full(
    query: str,
    context_for_llm: str,
) -> str:
    tokens = list(generate_stream(query, context_for_llm))
    return "".join(tokens)
