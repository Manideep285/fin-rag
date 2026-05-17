"""Worker entrypoint.

Runs two things in the same process:
1. HTTP server (FastAPI) exposing /embed, /rerank, /metrics, /health.
   The api container offloads model inference here without bundling torch.
2. Background poller draining pgmq queues across all projects:
   ingest_<pid> -> handle_ingest
   embed_<pid>  -> handle_embed
   eval_<pid>   -> handle_eval
"""
from __future__ import annotations
import logging
import threading
import time

import structlog
import uvicorn
from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, Histogram, generate_latest
from pydantic import BaseModel
from sqlalchemy import text
from starlette.responses import Response

from .config import settings
from .db import session_scope
from .embedder import embed_texts, rerank_pairs
from .jobs import handle_embed, handle_eval, handle_ingest


logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger("finrag.worker")


JOB_DURATION = Histogram(
    "worker_job_duration_seconds",
    "Worker job duration",
    ["queue"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120),
)


# ---------- HTTP API for model inference ---------------------------------

http = FastAPI(title="finrag-worker", version="0.1.0")


class EmbedRequest(BaseModel):
    texts: list[str]
    is_query: bool = False


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]


class RerankRequest(BaseModel):
    query: str
    texts: list[str]


class RerankResponse(BaseModel):
    scores: list[float]


@http.get("/health")
def health():
    return {"ok": True}


@http.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest):
    return EmbedResponse(embeddings=embed_texts(req.texts, is_query=req.is_query))


@http.post("/rerank", response_model=RerankResponse)
def rerank(req: RerankRequest):
    return RerankResponse(scores=rerank_pairs(req.query, req.texts))


@http.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------- Queue poller -------------------------------------------------

QUEUE_HANDLERS = {
    "ingest": handle_ingest,
    "embed": handle_embed,
    "eval": handle_eval,
}


def _list_queues():
    """Return [(prefix, queue_name)]."""
    with session_scope() as db:
        rows = db.execute(text("SELECT queue_name FROM pgmq.list_queues()")).all()
    out = []
    for (q,) in rows:
        for prefix in QUEUE_HANDLERS:
            if q.startswith(f"{prefix}_"):
                out.append((prefix, q))
                break
    return out


def _drain_queue(prefix: str, queue: str) -> int:
    handled = 0
    with session_scope() as db:
        rows = db.execute(
            text("SELECT msg_id, message FROM pgmq.read(:q, 60, 5)"),
            {"q": queue},
        ).mappings().all()
        msgs = [(r["msg_id"], r["message"]) for r in rows]
    for msg_id, payload in msgs:
        t0 = time.perf_counter()
        try:
            QUEUE_HANDLERS[prefix](dict(payload))
            with session_scope() as db:
                db.execute(text("SELECT pgmq.delete(:q, :id)"), {"q": queue, "id": msg_id})
            handled += 1
        except Exception as e:
            log.exception("job.failed", queue=queue, msg_id=msg_id, error=str(e))
            # Leave message; visibility timeout will return it.
        finally:
            JOB_DURATION.labels(queue=prefix).observe(time.perf_counter() - t0)
    return handled


def _poll_loop():
    log.info("worker.poller.start", interval=settings.worker_poll_interval)
    while True:
        try:
            queues = _list_queues()
            total = 0
            for prefix, q in queues:
                total += _drain_queue(prefix, q)
            if total == 0:
                time.sleep(settings.worker_poll_interval)
        except Exception as e:
            log.exception("worker.poller.error", error=str(e))
            time.sleep(settings.worker_poll_interval)


def main() -> None:
    t = threading.Thread(target=_poll_loop, daemon=True, name="pgmq-poller")
    t.start()
    log.info("worker.http.start", port=settings.worker_http_port)
    uvicorn.run(http, host="0.0.0.0", port=settings.worker_http_port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
