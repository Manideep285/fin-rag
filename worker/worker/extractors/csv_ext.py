from __future__ import annotations
import csv
from io import StringIO

from . import NormalizedDoc, PageContent


def extract(source_id: str, raw: bytes) -> NormalizedDoc:
    """CSV → one logical page per file, content treated as a single table.

    Enhanced for financial data:
    - Preserves column headers as structured metadata
    - Generates human-readable summary statistics
    - Keeps column alignment for better embedding quality
    """
    text = raw.decode("utf-8", errors="replace")
    reader = csv.reader(StringIO(text))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return NormalizedDoc(source_id=source_id, pages=[])

    headers = rows[0]
    data_rows = rows[1:]
    header_str = "\t".join(headers)

    # Build table text
    body = "\n".join("\t".join(r) for r in data_rows)
    table_text = f"{header_str}\n{body}"

    # Generate a structured summary for better retrieval
    summary_parts = [
        f"CSV Dataset with {len(data_rows)} rows and {len(headers)} columns.",
        f"Columns: {', '.join(headers)}.",
    ]

    # Add basic stats for numeric columns
    numeric_summaries = _summarize_numeric_columns(headers, data_rows)
    if numeric_summaries:
        summary_parts.append("Key Statistics:")
        summary_parts.extend(f"  - {s}" for s in numeric_summaries)

    summary_text = "\n".join(summary_parts)

    return NormalizedDoc(
        source_id=source_id,
        pages=[
            # Page 1: Summary (great for semantic search on "what data is in this file?")
            PageContent(
                page_num=1,
                text=summary_text,
                tables=[],
                section_title="CSV Summary",
                is_table=False,
            ),
            # Page 2: Full table data (used for chunking + structured queries)
            PageContent(
                page_num=2,
                text=f"CSV Data\n{table_text}",
                tables=[table_text],
                section_title="CSV Data",
                is_table=True,
            ),
        ],
    )


def _summarize_numeric_columns(
    headers: list[str], data_rows: list[list[str]], max_cols: int = 8
) -> list[str]:
    """Generate summary statistics for numeric columns."""
    summaries = []
    for col_idx, header in enumerate(headers[:max_cols]):
        values = []
        for row in data_rows:
            if col_idx < len(row):
                try:
                    val = row[col_idx].strip().replace(",", "").replace("$", "").replace("%", "")
                    if val:
                        values.append(float(val))
                except (ValueError, IndexError):
                    continue

        if len(values) >= 3:  # Need at least 3 values for meaningful stats
            total = sum(values)
            avg = total / len(values)
            min_val = min(values)
            max_val = max(values)
            summaries.append(
                f"{header}: min={min_val:,.2f}, max={max_val:,.2f}, "
                f"avg={avg:,.2f}, total={total:,.2f} ({len(values)} values)"
            )
    return summaries
