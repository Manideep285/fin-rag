from __future__ import annotations
import csv
from io import StringIO

from . import NormalizedDoc, PageContent


def extract(source_id: str, raw: bytes) -> NormalizedDoc:
    """CSV → one logical page per file, content treated as a single table."""
    text = raw.decode("utf-8", errors="replace")
    reader = csv.reader(StringIO(text))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return NormalizedDoc(source_id=source_id, pages=[])

    header = "\t".join(rows[0])
    body = "\n".join("\t".join(r) for r in rows[1:])
    table_text = f"{header}\n{body}"

    return NormalizedDoc(
        source_id=source_id,
        pages=[
            PageContent(
                page_num=1,
                text=f"CSV Data\n{table_text}",
                tables=[table_text],
                section_title="CSV",
                is_table=True,
            )
        ],
    )
