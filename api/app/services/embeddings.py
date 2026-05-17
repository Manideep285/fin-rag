"""Query-side embedding.

The api container does NOT load the embedding model in-process by default;
it calls the worker's HTTP embed endpoint (worker exposes /embed). This keeps
the api container lean (no torch/sentence-transformers).

Set EMBED_INPROC=1 in dev to load the model inside the api process.
"""
from __future__ import annotations
import os
from functools import lru_cache
from typing import Sequence

import httpx

from ..config import settings


WORKER_URL = os.getenv("WORKER_URL", "http://worker:9100")
INPROC = os.getenv("EMBED_INPROC", "0") == "1"


@lru_cache
def _model():
    from sentence_transformers import SentenceTransformer  # local import
    return SentenceTransformer(settings.embed_model)


async def embed_query(text: str) -> list[float]:
    # BGE expects an instruction prefix on queries.
    prefixed = f"Represent this sentence for searching relevant passages: {text}"
    if INPROC:
        return _model().encode(prefixed, normalize_embeddings=True).tolist()
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{WORKER_URL}/embed", json={"texts": [prefixed], "is_query": True})
        r.raise_for_status()
        return r.json()["embeddings"][0]
