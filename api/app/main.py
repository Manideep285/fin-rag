from __future__ import annotations
import time
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from .config import settings
from .logging_setup import configure_logging, log
from .routers import admin, auth, ingest, me, projects, query

configure_logging()

app = FastAPI(title="fin-rag API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        endpoint=request.url.path,
        method=request.method,
    )
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as e:
        log.exception("request.error", error=str(e))
        raise
    latency_ms = int((time.perf_counter() - t0) * 1000)
    log.info("request.done", status=response.status_code, latency_ms=latency_ms)
    response.headers["x-request-id"] = request_id
    return response


app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(me.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"ok": True, "llm_provider": settings.llm_provider}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
