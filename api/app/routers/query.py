from __future__ import annotations
import random
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import Principal, get_current_principal
from ..config import settings
from ..db import get_db
from ..guardrails import is_refusal, violates_guardrails
from ..logging_setup import log
from ..metrics import (
    QUERIES_TOTAL,
    QUERY_CONTEXT_TOKENS,
    QUERY_LATENCY,
    REFUSALS_TOTAL,
)
from ..models import Project, QueryLog, RefusalLog
from ..pgmq import send as pgmq_send
from ..rate_limit import check_rate_limit
from ..schemas import CitationOut, QueryRequest, QueryResponse
from ..services import context as ctx
from ..services import retrieval
from ..services.answer_synthesizer import StructuredResult, post_process_answer
from ..services.embeddings import embed_query
from ..services.financial_validator import validate_answer_numbers
from ..services.llm import chat_completion
from ..services.prompts import (
    build_hybrid_messages,
    build_messages,
    build_structured_messages,
)
from ..services.query_router import QueryMode, classify_query

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    request: Request,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    check_rate_limit(request)
    if str(body.project_id) != str(p.project_id):
        raise HTTPException(403, "project mismatch with token")

    request_id = str(uuid4())
    t0 = time.perf_counter()

    project = db.query(Project).filter(Project.id == p.project_id).first()
    if not project or not project.active_index_version:
        raise HTTPException(409, "project has no active index version yet")

    log_row = QueryLog(
        id=uuid4(),
        request_id=request_id,
        project_id=p.project_id,
        user_id=p.user_id,
        query=body.query,
        chunk_ids=[],
        created_at=datetime.now(timezone.utc),
    )

    # Guardrails
    if violates_guardrails(body.query):
        log_row.refused = True
        log_row.answer = "Refused by guardrails."
        log_row.status = 200
        log_row.latency_ms = int((time.perf_counter() - t0) * 1000)
        db.add(log_row)
        db.flush()
        db.add(RefusalLog(id=uuid4(), query_log_id=log_row.id, project_id=p.project_id,
                          reason="guardrail", created_at=datetime.now(timezone.utc)))
        db.commit()
        REFUSALS_TOTAL.labels(project_id=str(p.project_id), reason="guardrail").inc()
        QUERIES_TOTAL.labels(project_id=str(p.project_id), status="refused").inc()
        return QueryResponse(
            request_id=request_id,
            answer="I can't answer that request.",
            citations=[],
            refused=True,
            latency_ms=log_row.latency_ms,
            context_tokens=0,
        )

    # ---- Classify query mode ----
    has_structured = _check_structured_data(p.project_id)
    query_mode, confidence = await classify_query(body.query, has_structured)

    log.info(
        "query.mode_classified",
        request_id=request_id,
        mode=query_mode.value,
        confidence=confidence,
        has_structured=has_structured,
    )

    # ---- Execute the appropriate pipeline(s) ----
    if query_mode == QueryMode.STRUCTURED:
        answer, used, ctx_tokens, tokens_in, tokens_out, refused = await _handle_structured(
            project, body, p
        )
    elif query_mode == QueryMode.DOCUMENT:
        answer, used, ctx_tokens, tokens_in, tokens_out, refused = await _handle_document(
            project, body, p, db
        )
    else:  # HYBRID
        answer, used, ctx_tokens, tokens_in, tokens_out, refused = await _handle_hybrid(
            project, body, p, db
        )

    # ---- Financial post-processing ----
    if not refused and settings.financial_domain:
        answer, post_warnings = post_process_answer(answer, query_mode.value)

        # Numerical validation
        if settings.numerical_validation_enabled and used:
            validation = validate_answer_numbers(
                answer,
                [h.text for h in used],
            )
            if validation.warnings:
                log.info(
                    "query.numerical_validation",
                    request_id=request_id,
                    confidence=validation.confidence,
                    unverified=len(validation.unverified_numbers),
                )

    # ---- Finalize and log ----
    latency_ms = int((time.perf_counter() - t0) * 1000)
    QUERY_LATENCY.observe(latency_ms / 1000.0)

    log_row.answer = answer
    log_row.chunk_ids = [h.chunk_id for h in used]
    log_row.context_token_count = ctx_tokens
    log_row.num_chunks_used = len(used)
    log_row.llm_tokens_in = tokens_in
    log_row.llm_tokens_out = tokens_out
    log_row.latency_ms = latency_ms
    log_row.status = 200
    log_row.refused = refused
    db.add(log_row)
    db.flush()

    if refused:
        db.add(RefusalLog(id=uuid4(), query_log_id=log_row.id, project_id=p.project_id,
                          reason="no_context" if not used else "model_refusal",
                          created_at=datetime.now(timezone.utc)))
        REFUSALS_TOTAL.labels(project_id=str(p.project_id), reason="model").inc()

    # Sample async eval (§11)
    if used and random.random() < settings.eval_sample_rate:
        pgmq_send(db, "eval", p.project_id, {"query_log_id": str(log_row.id)})

    db.commit()
    QUERIES_TOTAL.labels(project_id=str(p.project_id), status="ok").inc()

    log.info("query.completed", request_id=request_id, latency_ms=latency_ms,
             mode=query_mode.value, num_chunks_used=len(used),
             context_tokens=ctx_tokens, refused=refused)

    return QueryResponse(
        request_id=request_id,
        answer=answer,
        citations=[
            CitationOut(
                chunk_id=h.chunk_id,
                source_id=h.source_id,
                source_name=h.source_name,
                page_num=h.page_num,
                section=h.section,
                text=h.text[:500],
                score=h.score,
            )
            for h in used
        ],
        refused=refused,
        latency_ms=latency_ms,
        context_tokens=ctx_tokens,
    )


# ---------------------------------------------------------------------------
# Pipeline handlers
# ---------------------------------------------------------------------------

async def _handle_document(project, body, p, db):
    """Original document RAG pipeline."""
    q_emb = await embed_query(body.query)
    bm25 = retrieval.bm25_search(
        db, p.project_id, project.active_index_version, body.query, settings.bm25_top_k
    )
    vec = retrieval.vector_search(
        db, p.project_id, project.active_index_version, q_emb, settings.vector_top_k
    )
    fused = retrieval.reciprocal_rank_fusion(
        bm25, vec, k=settings.rrf_k, top_n=settings.rerank_top_k
    )
    ranked = await retrieval.rerank(body.query, fused, top_n=settings.final_top_k)

    context_str, used, ctx_tokens = ctx.assemble_context(ranked)
    QUERY_CONTEXT_TOKENS.observe(ctx_tokens)

    if not used:
        return (
            "I don't have enough information in the project documents to answer this.",
            [], 0, 0, 0, True,
        )

    messages = build_messages(
        project.name,
        context_str,
        [m.model_dump() for m in body.conversation_history],
        body.query,
    )
    resp = await chat_completion(messages)
    answer = resp["choices"][0]["message"]["content"]
    usage = resp.get("usage", {}) or {}
    tokens_in = usage.get("prompt_tokens", 0)
    tokens_out = usage.get("completion_tokens", 0)
    refused = is_refusal(answer)

    return answer, used, ctx_tokens, tokens_in, tokens_out, refused


async def _handle_structured(project, body, p):
    """Text-to-SQL pipeline for structured data queries."""
    from ..services.text_to_sql import text_to_sql_query

    structured_result = await text_to_sql_query(p.project_id, body.query)

    if structured_result.error:
        # Fall back to document RAG if structured query fails
        log.info("query.structured_fallback", error=structured_result.error[:200])
        return (
            f"I couldn't query the structured data: {structured_result.error}. "
            "Please try rephrasing or ask a document-based question.",
            [], 0, 0, 0, False,
        )

    result_text = structured_result.to_text()

    messages = build_structured_messages(
        project_name=project.name,
        sql_query=structured_result.sql_query,
        data_source=structured_result.data_source,
        structured_results=result_text,
        context="",
        history=[m.model_dump() for m in body.conversation_history],
        query=body.query,
    )
    resp = await chat_completion(messages)
    answer = resp["choices"][0]["message"]["content"]
    usage = resp.get("usage", {}) or {}
    tokens_in = usage.get("prompt_tokens", 0)
    tokens_out = usage.get("completion_tokens", 0)

    return answer, [], 0, tokens_in, tokens_out, False


async def _handle_hybrid(project, body, p, db):
    """Hybrid pipeline: both document RAG + structured data."""
    from ..services.text_to_sql import text_to_sql_query

    # Run both pipelines concurrently
    # 1. Document RAG
    q_emb = await embed_query(body.query)
    bm25 = retrieval.bm25_search(
        db, p.project_id, project.active_index_version, body.query, settings.bm25_top_k
    )
    vec = retrieval.vector_search(
        db, p.project_id, project.active_index_version, q_emb, settings.vector_top_k
    )
    fused = retrieval.reciprocal_rank_fusion(
        bm25, vec, k=settings.rrf_k, top_n=settings.rerank_top_k
    )
    ranked = await retrieval.rerank(body.query, fused, top_n=settings.final_top_k)

    # 2. Structured data
    structured_result = None
    structured_text = ""
    if _check_structured_data(p.project_id):
        structured_result = await text_to_sql_query(p.project_id, body.query)
        if not structured_result.error:
            structured_text = structured_result.to_text()

    # Assemble hybrid context
    struct_ctx, doc_ctx, used, ctx_tokens = ctx.assemble_hybrid_context(
        ranked, structured_text
    )
    QUERY_CONTEXT_TOKENS.observe(ctx_tokens)

    if not used and not structured_text:
        return (
            "I don't have enough information in the project data or documents to answer this.",
            [], 0, 0, 0, True,
        )

    # Build hybrid prompt
    if structured_text and used:
        messages = build_hybrid_messages(
            project_name=project.name,
            structured_results=struct_ctx,
            context=doc_ctx,
            history=[m.model_dump() for m in body.conversation_history],
            query=body.query,
        )
    elif structured_text:
        messages = build_structured_messages(
            project_name=project.name,
            sql_query=structured_result.sql_query if structured_result else "",
            data_source=structured_result.data_source if structured_result else "",
            structured_results=struct_ctx,
            context="",
            history=[m.model_dump() for m in body.conversation_history],
            query=body.query,
        )
    else:
        messages = build_messages(
            project.name,
            doc_ctx,
            [m.model_dump() for m in body.conversation_history],
            body.query,
        )

    resp = await chat_completion(messages)
    answer = resp["choices"][0]["message"]["content"]
    usage = resp.get("usage", {}) or {}
    tokens_in = usage.get("prompt_tokens", 0)
    tokens_out = usage.get("completion_tokens", 0)
    refused = is_refusal(answer)

    return answer, used, ctx_tokens, tokens_in, tokens_out, refused


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_structured_data(project_id) -> bool:
    """Check if project has structured data available."""
    if not settings.structured_data_enabled:
        return False
    try:
        from ..services.schema_manager import has_structured_data
        return has_structured_data(project_id)
    except Exception:
        return False
