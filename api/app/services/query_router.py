"""Query Router — Classify incoming queries as structured, document, or hybrid.

Uses a lightweight LLM call to determine whether a user question should be
answered via:
  - "structured" → Text-to-SQL pipeline (SQL/CSV/tabular data)
  - "document"   → Document RAG pipeline (PDFs, reports, narrative text)
  - "hybrid"     → Both pipelines (needs exact numbers + narrative context)

Falls back to "hybrid" when confidence is low or router is disabled.
"""
from __future__ import annotations
import json
from enum import Enum

from ..config import settings
from ..logging_setup import log
from ..services.llm import chat_completion


class QueryMode(str, Enum):
    STRUCTURED = "structured"
    DOCUMENT = "document"
    HYBRID = "hybrid"


ROUTER_PROMPT = """You are a query classifier for a financial and consulting knowledge system.

The system has TWO data sources:
1. STRUCTURED DATA: SQL databases, CSV files, Excel spreadsheets with tabular financial data
   (revenue, expenses, client billing, project hours, transactions, account balances, etc.)
2. DOCUMENTS: PDF reports, consulting deliverables, policies, contracts, audit reports,
   meeting notes, narrative text with qualitative analysis.

Classify the user's query into one of three categories:

- "structured": The question asks for specific numbers, aggregations, comparisons, rankings,
  or filtering that requires querying tabular data.
  Examples: "What was Q4 revenue?", "Top 5 clients by billing", "Total expenses in 2024",
  "Show me projects over budget", "Average deal size by sector"

- "document": The question asks for narrative information, explanations, policies, qualitative
  analysis, or references to specific document content.
  Examples: "What does the audit report say about risk?", "Summarize the consulting methodology",
  "What are the compliance requirements?", "Explain the engagement approach"

- "hybrid": The question needs BOTH structured data AND narrative context, or is ambiguous.
  Examples: "Why did revenue decline in Q3?", "Explain the variance in project margins",
  "What factors affected client retention rates?"

Respond with ONLY a JSON object:
{{"mode": "structured"|"document"|"hybrid", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}
"""


async def classify_query(query: str, has_structured_sources: bool = True) -> tuple[QueryMode, float]:
    """Classify a query into structured, document, or hybrid mode.

    Args:
        query: The user's question.
        has_structured_sources: Whether the project has structured data sources.

    Returns:
        (mode, confidence) tuple.
    """
    # If router is disabled or no structured sources, default to document mode
    if not settings.query_router_enabled:
        return QueryMode.DOCUMENT, 1.0

    if not has_structured_sources:
        return QueryMode.DOCUMENT, 1.0

    # Quick heuristics before burning an LLM call
    mode = _heuristic_classify(query)
    if mode is not None:
        return mode, 0.85

    # LLM-based classification
    try:
        messages = [
            {"role": "system", "content": ROUTER_PROMPT},
            {"role": "user", "content": query},
        ]
        resp = await chat_completion(messages, max_tokens=150, temperature=0.0)
        content = resp["choices"][0]["message"]["content"].strip()

        # Parse JSON from response
        parsed = _parse_router_response(content)
        mode = QueryMode(parsed["mode"])
        confidence = float(parsed.get("confidence", 0.7))

        log.info(
            "query_router.classified",
            mode=mode.value,
            confidence=confidence,
            reasoning=parsed.get("reasoning", ""),
        )

        # If confidence is below threshold, default to hybrid
        if confidence < settings.query_router_confidence_threshold:
            return QueryMode.HYBRID, confidence

        return mode, confidence

    except Exception as e:
        log.warning("query_router.fallback", error=str(e))
        return QueryMode.HYBRID, 0.5


def _heuristic_classify(query: str) -> QueryMode | None:
    """Fast keyword-based pre-classification to avoid LLM calls for obvious cases."""
    q = query.lower().strip()

    # Strong structured indicators
    structured_signals = [
        "how much", "how many", "total", "sum of", "average", "count",
        "top ", "bottom ", "rank", "sort by", "group by",
        "greater than", "less than", "between", "more than", "fewer than",
        "revenue", "expense", "profit", "loss", "margin", "cost",
        "billing", "invoice", "transaction", "balance", "outstanding",
        "compare", "vs", "versus", "trend", "growth rate",
        "percentage", "ratio", "per ", "breakdown",
        "ytd", "mtd", "qtd", "year to date",
    ]

    # Strong document indicators
    document_signals = [
        "explain", "describe", "summarize", "what does", "what is the policy",
        "according to", "the report says", "the document",
        "methodology", "approach", "framework", "process",
        "compliance", "regulation", "requirement", "guideline",
        "recommendation", "finding", "conclusion", "audit opinion",
        "contract", "agreement", "terms", "clause",
    ]

    struct_score = sum(1 for s in structured_signals if s in q)
    doc_score = sum(1 for s in document_signals if s in q)

    if struct_score >= 2 and doc_score == 0:
        return QueryMode.STRUCTURED
    if doc_score >= 2 and struct_score == 0:
        return QueryMode.DOCUMENT

    return None  # ambiguous → use LLM


def _parse_router_response(content: str) -> dict:
    """Extract JSON from LLM response, handling various formats."""
    # Try direct JSON parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from markdown code block
    import re
    json_match = re.search(r"\{[^}]+\}", content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: look for mode keyword
    content_lower = content.lower()
    if "structured" in content_lower:
        return {"mode": "structured", "confidence": 0.6}
    if "document" in content_lower:
        return {"mode": "document", "confidence": 0.6}

    return {"mode": "hybrid", "confidence": 0.5}
