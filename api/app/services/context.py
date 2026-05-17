"""Context assembly: select and format retrieved chunks for the LLM prompt.

Takes ranked+reranked hits and assembles a context string within the token
budget configured in settings.  Returns the assembled text, the list of
hits that fit, and the total token count consumed.

Enhanced to handle both:
- Document RAG context (text chunks from PDFs, docs)
- Structured data context (SQL query results from tables/CSVs)
- Hybrid context (both combined)
"""
from __future__ import annotations
from typing import Optional, Sequence

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


def assemble_hybrid_context(
    hits: Sequence,
    structured_text: Optional[str] = None,
    max_tokens: int | None = None,
) -> tuple[str, str, list, int]:
    """Build context for hybrid mode: structured results + document chunks.

    Allocates token budget:
    - 40% for structured results (if present)
    - 60% for document chunks (or 100% if no structured results)

    Returns:
        (structured_context, document_context, used_hits, total_token_count)
    """
    budget = max_tokens or settings.context_max_tokens

    # If no structured data, give all budget to documents
    if not structured_text:
        doc_ctx, used, doc_tokens = assemble_context(hits, max_tokens=budget)
        return "", doc_ctx, used, doc_tokens

    # If no document hits, give all budget to structured data
    if not hits:
        struct_tokens = count_tokens(structured_text)
        if struct_tokens > budget:
            # Truncate structured results
            encoded = _enc().encode(structured_text)[:budget]
            structured_text = _enc().decode(encoded)
            struct_tokens = budget
        return structured_text, "", [], struct_tokens

    # Hybrid: split budget
    struct_budget = int(budget * 0.4)
    doc_budget = budget - struct_budget

    # Fit structured results
    struct_tokens = count_tokens(structured_text)
    if struct_tokens > struct_budget:
        encoded = _enc().encode(structured_text)[:struct_budget]
        structured_text = _enc().decode(encoded)
        struct_tokens = struct_budget
    else:
        # Give unused structured budget to documents
        doc_budget += (struct_budget - struct_tokens)

    # Fit document chunks
    doc_ctx, used, doc_tokens = assemble_context(hits, max_tokens=doc_budget)

    total_tokens = struct_tokens + doc_tokens
    return structured_text, doc_ctx, used, total_tokens
