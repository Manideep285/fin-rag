from __future__ import annotations
from io import BytesIO

import fitz  # pymupdf
import pdfplumber
from PIL import Image

from . import NormalizedDoc, PageContent


def _ocr(page: "fitz.Page") -> str:
    import pytesseract
    pix = page.get_pixmap(dpi=200)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return pytesseract.image_to_string(img)


def _tables_for_page(buf: bytes, page_index: int) -> list[str]:
    out: list[str] = []
    try:
        with pdfplumber.open(BytesIO(buf)) as pdf:
            page = pdf.pages[page_index]
            for t in page.extract_tables() or []:
                rows = ["\t".join((c or "").strip() for c in row) for row in t if any(row)]
                if rows:
                    out.append("\n".join(rows))
    except Exception:
        pass
    return out


def extract(source_id: str, raw: bytes) -> NormalizedDoc:
    pages: list[PageContent] = []
    doc = fitz.open(stream=raw, filetype="pdf")
    raw_for_tables = raw
    for i, page in enumerate(doc):
        text = page.get_text("text") or ""
        if len(text.strip()) < 50:
            text = _ocr(page)
        tables = _tables_for_page(raw_for_tables, i)
        pages.append(PageContent(page_num=i + 1, text=text, tables=tables))
    return NormalizedDoc(source_id=source_id, pages=pages)
