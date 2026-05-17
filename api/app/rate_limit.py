from __future__ import annotations
from datetime import datetime, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy import text

from .db import SessionLocal

# (max_requests, window_seconds) per endpoint.
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/query": (20, 60),
    "/auth/signup": (5, 600),
    "/auth/login": (10, 60),
    "/api/ingest": (10, 60),
}


def check_rate_limit(request: Request) -> None:
    path = request.url.path
    cfg = RATE_LIMITS.get(path)
    if not cfg:
        return
    max_req, window_s = cfg
    ip = request.client.host if request.client else "unknown"
    # Truncate window to (now - now % window_s) so callers within the same
    # window share a row.
    now = datetime.now(timezone.utc).replace(microsecond=0)
    window_start = now.replace(second=0)  # 1-minute resolution; fine-grained windowing
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                """
                INSERT INTO rate_limits (ip, endpoint, window_start, count)
                VALUES (:ip, :ep, :ws, 1)
                ON CONFLICT (ip, endpoint, window_start)
                DO UPDATE SET count = rate_limits.count + 1
                RETURNING count
                """
            ),
            {"ip": ip, "ep": path, "ws": window_start},
        ).scalar_one()
        db.commit()
        if result > max_req:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"rate limit exceeded ({max_req} per {window_s}s)",
            )
    finally:
        db.close()
