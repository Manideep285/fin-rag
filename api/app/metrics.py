from __future__ import annotations
from prometheus_client import Counter, Gauge, Histogram

QUERY_LATENCY = Histogram(
    "query_latency_seconds",
    "End-to-end /api/query latency",
    buckets=(0.1, 0.25, 0.5, 1, 2, 4, 8, 16, 32),
)
QUERY_CONTEXT_TOKENS = Histogram(
    "query_context_tokens",
    "Tokens of context assembled for the LLM",
    buckets=(100, 250, 500, 1000, 1500, 2000, 2500, 3000, 4000),
)
EMBED_DURATION = Histogram("embed_job_duration_seconds", "Worker embed job duration")
ACTIVE_INDEX_VERSION = Gauge(
    "active_index_version", "Currently active index version", ["project_id"]
)
CHUNKS_TOTAL = Gauge("chunks_total", "Total chunks per project", ["project_id"])
EVAL_GROUNDEDNESS = Histogram(
    "eval_groundedness_score", "Async groundedness scores", buckets=(0, 0.25, 0.5, 0.75, 0.9, 1.0)
)
QUERIES_TOTAL = Counter("queries_total", "Total queries", ["project_id", "status"])
REFUSALS_TOTAL = Counter("refusals_total", "Refused responses", ["project_id", "reason"])
