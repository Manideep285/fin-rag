"""Hybrid retrieval: BM25 + pgvector → RRF → cross-encoder rerank.

Implements §8 of the architecture plan.
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings


@dataclass
class Hit:
    chunk_id: UUID
    source_id: UUID
    source_name: str
    project_id: UUID
    text: str
    page_num: int | None
    section: str | None
    score: float = 0.0
    bm25_rank: int | None = None
    vec_rank: int | None = None


WORKER_URL = os.getenv("WORKER_URL", "http://worker:9100")
RERANK_INPROC = os.getenv("RERANK_INPROC", "0") == "1"


def bm25_search(
    db: Session, project_id: UUID, index_version: int, query: str, k: int
) -> list[Hit]:
    rows = db.execute(
        text(
            """
            SELECT c.id, c.source_id, s.name AS source_name, c.project_id,
                   c.text, c.page_num, c.section,
                   ts_rank(to_tsvector('english', c.text),
                           plainto_tsquery('english', :q)) AS score
            FROM chunks c
            JOIN sources s ON s.id = c.source_id
            WHERE c.project_id = :pid
              AND c.index_version = :iv
              AND to_tsvector('english', c.text) @@ plainto_tsquery('english', :q)
            ORDER BY score DESC
            LIMIT :k
            """
        ),
        {"pid": str(project_id), "iv": index_version, "q": query, "k": k},
    ).mappings().all()
    return [
        Hit(
            chunk_id=r["id"],
            source_id=r["source_id"],
            source_name=r["source_name"],
            project_id=r["project_id"],
            text=r["text"],
            page_num=r["page_num"],
            section=r["section"],
            score=float(r["score"] or 0.0),
            bm25_rank=i + 1,
        )
        for i, r in enumerate(rows)
    ]


def vector_search(
    db: Session,
    project_id: UUID,
    index_version: int,
    embedding: Sequence[float],
    k: int,
) -> list[Hit]:
    rows = db.execute(
        text(
            """
            SELECT c.id, c.source_id, s.name AS source_name, c.project_id,
                   c.text, c.page_num, c.section,
                   1 - (c.embedding <=> CAST(:emb AS vector)) AS score
            FROM chunks c
            JOIN sources s ON s.id = c.source_id
            WHERE c.project_id = :pid
              AND c.index_version = :iv
              AND c.embedding IS NOT NULL
            ORDER BY c.embedding <=> CAST(:emb AS vector)
            LIMIT :k
            """
        ),
        {
            "pid": str(project_id),
            "iv": index_version,
            "emb": str(list(embedding)),
            "k": k,
        },
    ).mappings().all()
    return [
        Hit(
            chunk_id=r["id"],
            source_id=r["source_id"],
            source_name=r["source_name"],
            project_id=r["project_id"],
            text=r["text"],
            page_num=r["page_num"],
            section=r["section"],
            score=float(r["score"] or 0.0),
            vec_rank=i + 1,
        )
        for i, r in enumerate(rows)
    ]


def reciprocal_rank_fusion(
    bm25: list[Hit], vec: list[Hit], k: int = 60, top_n: int = 10
) -> list[Hit]:
    """Merge two ranked lists using RRF (k=60 is the standard default)."""
    by_id: dict[UUID, Hit] = {}
    for h in bm25:
        by_id[h.chunk_id] = Hit(**{**h.__dict__})
    for h in vec:
        if h.chunk_id in by_id:
            by_id[h.chunk_id].vec_rank = h.vec_rank
        else:
            by_id[h.chunk_id] = Hit(**{**h.__dict__})

    scored: list[Hit] = []
    for h in by_id.values():
        rrf = 0.0
        if h.bm25_rank is not None:
            rrf += 1.0 / (k + h.bm25_rank)
        if h.vec_rank is not None:
            rrf += 1.0 / (k + h.vec_rank)
        h.score = rrf
        scored.append(h)
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:top_n]


@lru_cache
def _reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(settings.reranker_model)


async def rerank(query: str, hits: list[Hit], top_n: int) -> list[Hit]:
    if not hits:
        return []
    pairs = [(query, h.text) for h in hits]
    if RERANK_INPROC:
        scores = _reranker().predict(pairs).tolist()
    else:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{WORKER_URL}/rerank", json={"query": query, "texts": [h.text for h in hits]})
            r.raise_for_status()
            scores = r.json()["scores"]
    for h, s in zip(hits, scores):
        h.score = float(s)
    hits.sort(key=lambda x: x.score, reverse=True)
    return hits[:top_n]
