from __future__ import annotations
from . import NormalizedDoc, PageContent


def extract(source_id: str, raw: bytes) -> NormalizedDoc:
    text = raw.decode("utf-8", errors="replace")
    return NormalizedDoc(source_id=source_id, pages=[PageContent(page_num=1, text=text)])
