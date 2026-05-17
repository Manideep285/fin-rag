from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PageContent:
    page_num: int
    text: str
    tables: list[str] = field(default_factory=list)
    section_title: Optional[str] = None
    is_header: bool = False
    is_table: bool = False


@dataclass
class NormalizedDoc:
    source_id: str
    pages: list[PageContent]


def route(extension: str):
    ext = extension.lower()
    if ext == ".pdf":
        from . import pdf
        return pdf.extract
    if ext == ".docx":
        from . import docx
        return docx.extract
    if ext == ".xlsx":
        from . import xlsx
        return xlsx.extract
    if ext == ".pptx":
        from . import pptx
        return pptx.extract
    if ext in (".txt", ".md"):
        from . import text as text_mod
        return text_mod.extract
    raise ValueError(f"unsupported extension {ext}")
