"""Context assembly: select and format retrieved chunks for the LLM prompt.

Takes ranked+reranked hits and assembles a context string within the token
budget configured in settings.  Returns the assembled text, the list of
hits that fit, and the total token count consumed.

Implements the token-budget section of §8.
"""
from __future__ import annotations
from typing import Sequence

import tiktoken
from functools import lru_cache

from ..config import settings


@lru_cache
def _enc():
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_enc().encode(text))


def assemble_context(
    hits: Sequence,  # list of Hit dataclass from retrieval
    max_tokens: int | None = None,
) -> tuple[str, list, int]:
    """Build a context string from ranked hits, respecting the token budget.

    Returns:
        (context_string, used_hits, total_token_count)
    """
    budget = max_tokens or settings.context_max_tokens
    used = []
    parts: list[str] = []
    total_tokens = 0

    for h in hits:
        chunk_text = f"[Source: {h.source_name}"
        if h.page_num:
            chunk_text += f", Page {h.page_num}"
        if h.section:
            chunk_text += f", Section: {h.section}"
        chunk_text += f"]\n{h.text}\n"

        chunk_tokens = count_tokens(chunk_text)
        if total_tokens + chunk_tokens > budget:
            # If we haven't included anything yet and this single chunk is
            # over budget, truncate it so the user still gets *some* context.
            if not used:
                remaining = budget - total_tokens
                if remaining > 50:
                    encoded = _enc().encode(chunk_text)[:remaining]
                    chunk_text = _enc().decode(encoded)
                    chunk_tokens = remaining
                else:
                    break
            else:
                break

        parts.append(chunk_text)
        used.append(h)
        total_tokens += chunk_tokens

    return "\n---\n".join(parts), used, total_tokens
