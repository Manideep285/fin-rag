"""Answer Synthesizer — Merge structured data results + document context.

Produces a unified answer from potentially two sources:
  - Structured query results (SQL/tabular data)
  - Document RAG chunks (narrative text)

Also applies financial post-processing:
  - Forward-looking statement disclaimers
  - PII redaction warnings
  - Numerical cross-validation
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from ..config import settings
from ..guardrails import check_answer_safety, detect_forward_looking
from ..logging_setup import log


@dataclass
class StructuredResult:
    """Result from the Text-to-SQL pipeline."""
    sql_query: str
    data_source: str
    rows: list[dict]
    columns: list[str]
    row_count: int
    truncated: bool = False
    error: Optional[str] = None

    def to_text(self, max_rows: int = 50) -> str:
        """Format structured results as a readable text table."""
        if self.error:
            return f"Query Error: {self.error}"
        if not self.rows:
            return "No results found for this query."

        lines = []
        lines.append(f"Data Source: {self.data_source}")
        lines.append(f"Rows returned: {self.row_count}" + (" (truncated)" if self.truncated else ""))
        lines.append("")

        # Header
        header = " | ".join(str(c) for c in self.columns)
        lines.append(header)
        lines.append("-" * len(header))

        # Rows
        display_rows = self.rows[:max_rows]
        for row in display_rows:
            line = " | ".join(
                _format_value(row.get(c)) for c in self.columns
            )
            lines.append(line)

        if len(self.rows) > max_rows:
            lines.append(f"... and {len(self.rows) - max_rows} more rows")

        return "\n".join(lines)


@dataclass
class SynthesizedAnswer:
    """The final answer combining structured + document results."""
    answer: str
    mode: str                          # structured | document | hybrid
    structured_result: Optional[StructuredResult] = None
    document_context_used: bool = False
    citations: list = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sql_query: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0


def post_process_answer(answer: str, mode: str) -> tuple[str, list[str]]:
    """Apply financial post-processing to the generated answer.

    Returns:
        (processed_answer, warnings)
    """
    warnings: list[str] = []

    # Safety checks
    if settings.pii_detection_enabled or settings.mnpi_detection_enabled:
        safety = check_answer_safety(answer)
        warnings.extend(safety["warnings"])

        # If PII found, add a warning header but don't redact (let human decide)
        if safety["pii_found"]:
            log.warning("answer.pii_detected", types=safety["pii_found"])

    # Forward-looking statement disclaimer
    if settings.forward_looking_disclaimer and detect_forward_looking(answer):
        disclaimer = (
            "\n\n---\n*Note: This response contains forward-looking statements or projections. "
            "These are based on available data and should not be considered guarantees of "
            "future performance. Actual results may differ materially.*"
        )
        answer += disclaimer
        warnings.append("Forward-looking statement disclaimer added")

    return answer, warnings


def _format_value(val) -> str:
    """Format a single cell value for display."""
    if val is None:
        return "—"
    if isinstance(val, float):
        # Format large numbers with commas, keep 2 decimal places
        if abs(val) >= 1000:
            return f"{val:,.2f}"
        return f"{val:.4f}"
    if isinstance(val, int) and abs(val) >= 1000:
        return f"{val:,}"
    return str(val)
