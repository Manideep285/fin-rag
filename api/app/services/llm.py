"""LLM interface — single entry point for all completion calls.

Section 0 fallback contract: callers never talk to vLLM/OpenAI directly.
Flip LLM_PROVIDER to switch backends. The interface is OpenAI-compatible so
both vLLM (--openai-compat) and any cloud OpenAI-style endpoint work.
"""
from __future__ import annotations
from typing import AsyncIterator, Iterable

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings
from ..logging_setup import log


class LLMError(RuntimeError):
    pass


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.llm_base_url.rstrip("/"),
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        timeout=httpx.Timeout(60.0, connect=10.0),
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
async def chat_completion(
    messages: list[dict],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> dict:
    payload = {
        "model": model or settings.llm_model,
        "messages": messages,
        "max_tokens": max_tokens or settings.llm_max_tokens,
        "temperature": settings.llm_temperature if temperature is None else temperature,
        "stream": False,
    }
    async with _client() as c:
        r = await c.post("/chat/completions", json=payload)
        if r.status_code >= 400:
            log.error("llm_error", status=r.status_code, body=r.text[:500])
            raise LLMError(f"LLM {r.status_code}: {r.text[:200]}")
        return r.json()


async def chat_completion_stream(
    messages: list[dict],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> AsyncIterator[str]:
    payload = {
        "model": model or settings.llm_model,
        "messages": messages,
        "max_tokens": max_tokens or settings.llm_max_tokens,
        "temperature": settings.llm_temperature if temperature is None else temperature,
        "stream": True,
    }
    async with _client() as c:
        async with c.stream("POST", "/chat/completions", json=payload) as r:
            if r.status_code >= 400:
                body = await r.aread()
                raise LLMError(f"LLM {r.status_code}: {body[:200].decode('utf-8', 'ignore')}")
            async for line in r.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                import json as _json
                try:
                    obj = _json.loads(data)
                except Exception:
                    continue
                delta = (
                    obj.get("choices", [{}])[0]
                    .get("delta", {})
                    .get("content")
                )
                if delta:
                    yield delta
