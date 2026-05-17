from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import Principal, get_current_principal
from ..db import get_db
from ..models import QueryLog

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("/queries")
def my_queries(
    limit: int = 50,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(QueryLog)
        .filter(
            QueryLog.project_id == p.project_id,
            QueryLog.user_id == p.user_id,
        )
        .order_by(QueryLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(r.id),
            "query": r.query,
            "answer": r.answer,
            "refused": r.refused,
            "latency_ms": r.latency_ms,
            "num_chunks_used": r.num_chunks_used,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
