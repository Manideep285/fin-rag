from __future__ import annotations
import re

GUARDRAIL_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore previous instructions",
        r"system prompt",
        r"jailbreak",
        r"repeat the context verbatim",
        r"reveal (your )?instructions",
    ]
]

REFUSAL_PHRASE = "I don't have enough information in the project documents to answer this."


def violates_guardrails(query: str) -> bool:
    return any(p.search(query) for p in GUARDRAIL_PATTERNS)


def is_refusal(answer: str) -> bool:
    return REFUSAL_PHRASE.lower() in answer.lower()
