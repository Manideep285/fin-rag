"""Financial Validator — Post-processing verification for numerical accuracy.

Validates LLM-generated answers against source data to catch:
- Fabricated/hallucinated numbers
- Incorrect calculations
- Misattributed figures
- Currency/unit mismatches
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

from ..config import settings
from ..logging_setup import log


@dataclass
class ValidationResult:
    """Result of answer validation."""
    is_valid: bool = True
    verified_numbers: list[str] = field(default_factory=list)
    unverified_numbers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence: float = 1.0


# Regex to extract numerical values from text
NUMBER_PATTERNS = [
    # Currency values: $1,234.56, €100M, £2.5B
    re.compile(r"[\$€£¥₹][\s]?[\d,]+(?:\.\d+)?(?:\s?[KMBTkmbt](?:illion)?)?", re.IGNORECASE),
    # Percentage: 15.3%, 200 bps
    re.compile(r"\d+(?:\.\d+)?%"),
    re.compile(r"\d+(?:\.\d+)?\s*(?:basis\s+points|bps)", re.IGNORECASE),
    # Plain numbers with commas: 1,234,567
    re.compile(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b"),
    # Decimal numbers: 123.45
    re.compile(r"\b\d+\.\d+\b"),
    # Large round numbers with suffix: 100M, 2.5B, 500K
    re.compile(r"\b\d+(?:\.\d+)?\s?[KMBTkmbt](?:illion)?\b", re.IGNORECASE),
]


def extract_numbers_from_text(text: str) -> list[str]:
    """Extract all numerical values from text."""
    numbers = []
    for pattern in NUMBER_PATTERNS:
        matches = pattern.findall(text)
        numbers.extend(matches)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for n in numbers:
        normalized = n.strip()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def normalize_number(text: str) -> Optional[float]:
    """Normalize a number string to a float for comparison."""
    try:
        cleaned = text.strip()
        # Remove currency symbols
        cleaned = re.sub(r"[\$€£¥₹]", "", cleaned)
        # Remove commas
        cleaned = cleaned.replace(",", "")
        # Handle suffixes
        multipliers = {
            "k": 1e3, "thousand": 1e3,
            "m": 1e6, "million": 1e6,
            "b": 1e9, "billion": 1e9,
            "t": 1e12, "trillion": 1e12,
        }
        for suffix, mult in multipliers.items():
            if cleaned.lower().endswith(suffix):
                cleaned = cleaned[:len(cleaned) - len(suffix)].strip()
                return float(cleaned) * mult

        # Handle percentage
        if cleaned.endswith("%"):
            return float(cleaned[:-1])

        # Handle basis points
        bps_match = re.match(r"([\d.]+)\s*(?:bps|basis\s*points)", cleaned, re.IGNORECASE)
        if bps_match:
            return float(bps_match.group(1))

        return float(cleaned)
    except (ValueError, TypeError):
        return None


def validate_answer_numbers(
    answer: str,
    context_chunks: list[str],
    structured_results: Optional[str] = None,
) -> ValidationResult:
    """Validate that numbers in the answer exist in the source material.

    Args:
        answer: The LLM-generated answer.
        context_chunks: List of document chunk texts used as context.
        structured_results: Optional formatted structured query results.

    Returns:
        ValidationResult with verified/unverified numbers and warnings.
    """
    if not settings.numerical_validation_enabled:
        return ValidationResult()

    answer_numbers = extract_numbers_from_text(answer)
    if not answer_numbers:
        return ValidationResult()  # No numbers to validate

    # Build source text pool
    source_text = " ".join(context_chunks)
    if structured_results:
        source_text += " " + structured_results

    source_numbers = extract_numbers_from_text(source_text)

    # Normalize for comparison
    answer_normalized = {
        n: normalize_number(n) for n in answer_numbers
    }
    source_normalized = {
        normalize_number(n) for n in source_numbers
        if normalize_number(n) is not None
    }

    verified = []
    unverified = []
    warnings = []

    for num_text, num_val in answer_normalized.items():
        if num_val is None:
            continue

        # Check exact match or close match (within 0.1% tolerance for rounding)
        found = False
        for src_val in source_normalized:
            if src_val == 0 and num_val == 0:
                found = True
                break
            if src_val != 0 and abs(num_val - src_val) / abs(src_val) < 0.001:
                found = True
                break

        if found:
            verified.append(num_text)
        else:
            unverified.append(num_text)

    if unverified:
        warnings.append(
            f"⚠️ {len(unverified)} number(s) in the answer could not be verified "
            f"against source data: {', '.join(unverified[:5])}"
        )
        if len(unverified) > 5:
            warnings.append(f"  ... and {len(unverified) - 5} more")

    # Calculate confidence
    total = len(verified) + len(unverified)
    confidence = len(verified) / total if total > 0 else 1.0

    if confidence < 0.5:
        warnings.append(
            "❌ Less than 50% of numbers could be verified — answer may contain hallucinated figures."
        )

    result = ValidationResult(
        is_valid=confidence >= 0.5,
        verified_numbers=verified,
        unverified_numbers=unverified,
        warnings=warnings,
        confidence=confidence,
    )

    log.info(
        "financial_validator.validated",
        total_numbers=total,
        verified=len(verified),
        unverified=len(unverified),
        confidence=confidence,
    )

    return result
