"""Embedding + reranker singletons used by the worker (in-process & HTTP)."""
from __future__ import annotations
from functools import lru_cache
from typing import Sequence

import torch
from sentence_transformers import CrossEncoder, SentenceTransformer

from .config import settings


@lru_cache
def embed_model() -> SentenceTransformer:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return SentenceTransformer(settings.embed_model, device=device)


@lru_cache
def cross_encoder() -> CrossEncoder:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return CrossEncoder(settings.reranker_model, device=device)


def embed_texts(texts: Sequence[str], is_query: bool = False) -> list[list[float]]:
    if is_query:
        # BGE instruction prefix already applied upstream.
        pass
    arr = embed_model().encode(
        list(texts),
        batch_size=64,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in arr]


def rerank_pairs(query: str, texts: Sequence[str]) -> list[float]:
    if not texts:
        return []
    pairs = [(query, t) for t in texts]
    return [float(s) for s in cross_encoder().predict(pairs)]
