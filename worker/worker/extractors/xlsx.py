from __future__ import annotations
from io import BytesIO

from openpyxl import load_workbook

from . import NormalizedDoc, PageContent


def extract(source_id: str, raw: bytes) -> NormalizedDoc:
    """Each sheet → one logical 'page'. Each contiguous block of rows is a table.
    The header row is included in every chunk derived from that block (chunker
    repeats it when splitting; here we just emit the full table)."""
    wb = load_workbook(BytesIO(raw), data_only=True, read_only=True)
    pages: list[PageContent] = []

    for idx, ws in enumerate(wb.worksheets):
        rows_iter = ws.iter_rows(values_only=True)
        rows = [list(r) for r in rows_iter]
        rows = [r for r in rows if any(c is not None and str(c).strip() for c in r)]
        if not rows:
            continue
        header = rows[0]
        header_str = "\t".join(str(c) if c is not None else "" for c in header)
        body = "\n".join(
            "\t".join(str(c) if c is not None else "" for c in r) for r in rows[1:]
        )
        table_text = f"{header_str}\n{body}"
        pages.append(
            PageContent(
                page_num=idx + 1,
                text=f"Sheet: {ws.title}\n{table_text}",
                tables=[table_text],
                section_title=ws.title,
                is_table=True,
            )
        )
    return NormalizedDoc(source_id=source_id, pages=pages)
