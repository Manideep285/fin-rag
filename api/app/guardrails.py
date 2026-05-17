"""Guardrails — Financial safety, PII detection, SQL injection prevention.

Covers:
- Prompt injection / jailbreak detection (original)
- Financial PII detection (SSN, account numbers, etc.)
- Material Non-Public Information (MNPI) indicators
- SQL injection prevention for structured queries
- Forward-looking statement detection
"""
from __future__ import annotations
import re
from typing import Optional

# ---------------------------------------------------------------------------
# Prompt injection guardrails (original + extended)
# ---------------------------------------------------------------------------

GUARDRAIL_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore previous instructions",
        r"system prompt",
        r"jailbreak",
        r"repeat the context verbatim",
        r"reveal (your )?instructions",
        r"ignore all prior",
        r"disregard (your |the )?rules",
        r"pretend you (are|can)",
        r"act as (a |an )?unrestricted",
    ]
]

REFUSAL_PHRASE = "I don't have enough information in the project documents to answer this."


def violates_guardrails(query: str) -> bool:
    return any(p.search(query) for p in GUARDRAIL_PATTERNS)


def is_refusal(answer: str) -> bool:
    return REFUSAL_PHRASE.lower() in answer.lower()


# ---------------------------------------------------------------------------
# Financial PII detection
# ---------------------------------------------------------------------------

PII_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b\d{3}-\d{2}-\d{4}\b",           # SSN
        r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",  # Credit card
        r"\baccount\s*#?\s*\d{8,}\b",         # Account number
        r"\brouting\s*#?\s*\d{9}\b",          # Routing number
        r"\bein\s*:?\s*\d{2}-\d{7}\b",        # EIN
        r"\btax\s*id\s*:?\s*\d{2}-\d{7}\b",  # Tax ID
    ]
]


def contains_pii(text: str) -> list[str]:
    """Return list of PII types detected in text. Empty list = clean."""
    found = []
    labels = ["SSN", "credit_card", "account_number", "routing_number", "EIN", "tax_id"]
    for pattern, label in zip(PII_PATTERNS, labels):
        if pattern.search(text):
            found.append(label)
    return found


# ---------------------------------------------------------------------------
# MNPI (Material Non-Public Information) indicators
# ---------------------------------------------------------------------------

MNPI_INDICATORS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bpre-?announcement\b",
        r"\bnot\s+(yet\s+)?public(ly)?\s+(disclosed|announced|released)",
        r"\bembargoed\b",
        r"\bconfidential\s+(draft|memo|report)",
        r"\binsider\s+(information|trading)",
        r"\bpending\s+(merger|acquisition|deal|transaction)",
        r"\bblackout\s+period\b",
        r"\bnon-?public\s+information\b",
    ]
]


def has_mnpi_indicators(text: str) -> bool:
    """Check if text contains indicators of material non-public information."""
    return any(p.search(text) for p in MNPI_INDICATORS)


# ---------------------------------------------------------------------------
# SQL injection prevention
# ---------------------------------------------------------------------------

SQL_DANGEROUS_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(DROP|ALTER|CREATE|TRUNCATE|RENAME)\b",
        r"\b(INSERT|UPDATE|DELETE|MERGE)\b",
        r"\b(GRANT|REVOKE)\b",
        r"\b(EXEC|EXECUTE|xp_)\b",
        r";\s*(DROP|ALTER|DELETE|UPDATE|INSERT)",   # chained statements
        r"--\s*$",                                    # SQL comments at end
        r"/\*.*\*/",                                  # Block comments
        r"\bUNION\s+ALL\s+SELECT\b",                 # Union injection
        r"\bINTO\s+OUTFILE\b",                        # File write
        r"\bLOAD_FILE\b",                             # File read
    ]
]


def is_safe_sql(sql: str) -> tuple[bool, Optional[str]]:
    """Validate that generated SQL is read-only and safe to execute.

    Returns:
        (is_safe, reason) — reason is None if safe, otherwise explanation.
    """
    # Strip whitespace and normalize
    normalized = " ".join(sql.split())

    for pattern in SQL_DANGEROUS_PATTERNS:
        match = pattern.search(normalized)
        if match:
            return False, f"Dangerous SQL pattern detected: {match.group()}"

    # Must start with SELECT or WITH (CTE)
    stripped = normalized.lstrip().upper()
    if not (stripped.startswith("SELECT") or stripped.startswith("WITH")):
        return False, f"SQL must start with SELECT or WITH, got: {stripped[:30]}"

    # No multiple statements (semicolon followed by another statement)
    parts = [p.strip() for p in normalized.split(";") if p.strip()]
    if len(parts) > 1:
        return False, "Multiple SQL statements not allowed"

    return True, None


# ---------------------------------------------------------------------------
# Forward-looking statement detection
# ---------------------------------------------------------------------------

FORWARD_LOOKING_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(forecast|projected|estimated|expected|anticipated)\b",
        r"\b(guidance|outlook|target|goal)\b",
        r"\bforward-?looking\b",
        r"\b(will|shall|may|might|could)\s+(increase|decrease|grow|decline|reach|achieve)",
        r"\b(FY|CY|fiscal\s+year)\s*20\d{2}\s*(estimate|projection|forecast|target)",
    ]
]


def detect_forward_looking(text: str) -> bool:
    """Check if text contains forward-looking statements."""
    return any(p.search(text) for p in FORWARD_LOOKING_PATTERNS)


# ---------------------------------------------------------------------------
# Composite safety check for answers
# ---------------------------------------------------------------------------

def check_answer_safety(answer: str) -> dict:
    """Run all safety checks on a generated answer.

    Returns dict with:
        - pii_found: list of PII types
        - has_mnpi: bool
        - has_forward_looking: bool
        - warnings: list of human-readable warnings
    """
    pii = contains_pii(answer)
    mnpi = has_mnpi_indicators(answer)
    forward = detect_forward_looking(answer)

    warnings = []
    if pii:
        warnings.append(f"⚠️ PII detected in answer: {', '.join(pii)}")
    if mnpi:
        warnings.append("⚠️ Answer may contain material non-public information (MNPI)")
    if forward:
        warnings.append("ℹ️ Answer contains forward-looking statements — may require disclaimer")

    return {
        "pii_found": pii,
        "has_mnpi": mnpi,
        "has_forward_looking": forward,
        "warnings": warnings,
    }
