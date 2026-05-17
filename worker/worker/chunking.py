"""Hierarchical sentence-aware chunking (§6).

Hard boundaries: section heading, table start/end, page break.
Soft boundaries: sentence (spaCy `en_core_web_sm`).
Target ~350 tokens, max 400, overlap ~40, min 50.
Tables are emitted whole up to 600 tokens; if larger, row-grouped with header
repeated.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache

import tiktoken

from .config import settings
from .extractors import NormalizedDoc, PageContent


@dataclass
class Chunk:
    text: str
    prefixed_text: str
    token_count: int
    page_num: int | None
    section: str | None
    is_table: bool
    chunk_index: int


@lru_cache
def _enc():
    return tiktoken.get_encoding("cl100k_base")


@lru_cache
def _nlp():
    import spacy
    return spacy.load("en_core_web_sm", disable=["tagger", "parser", "ner", "lemmatizer"])


def _sentences(text: str) -> list[str]:
    nlp = _nlp()
    nlp.add_pipe("sentencizer") if "sentencizer" not in nlp.pipe_names else None
    return [s.text.strip() for s in nlp(text).sents if s.text.strip()]


def _tok_len(s: str) -> int:
    return len(_enc().encode(s))


def _prefix(project: str, section: str | None, page: int | None) -> str:
    return f"[Project: {project}] [Section: {section or ''}] [Page: {page or ''}]\n"


def _split_table(table_text: str, max_tokens: int = 600) -> list[str]:
    if _tok_len(table_text) <= max_tokens:
        return [table_text]
    lines = table_text.splitlines()
    if not lines:
        return [table_text]
    header = lines[0]
    body = lines[1:]
    out: list[str] = []
    current = [header]
    current_tokens = _tok_len(header)
    for row in body:
        rt = _tok_len(row)
        if current_tokens + rt > max_tokens and len(current) > 1:
            out.append("\n".join(current))
            current = [header, row]
            current_tokens = _tok_len(header) + rt
        else:
            current.append(row)
            current_tokens += rt
    if len(current) > 1:
        out.append("\n".join(current))
    return out


def chunk_document(doc: NormalizedDoc, project_name: str) -> list[Chunk]:
    target = settings.chunk_target_tokens
    overlap = settings.chunk_overlap_tokens
    min_tokens = settings.chunk_min_tokens
    max_tokens = settings.chunk_max_tokens

    chunks: list[Chunk] = []
    idx = 0

    for page in doc.pages:
        # Tables first — emit each as its own chunk(s), header preserved.
        for tbl in page.tables:
            for piece in _split_table(tbl):
                if _tok_len(piece) < min_tokens:
                    continue
                prefix = _prefix(project_name, page.section_title, page.page_num)
                chunks.append(
                    Chunk(
                        text=piece,
                        prefixed_text=prefix + piece,
                        token_count=_tok_len(piece),
                        page_num=page.page_num,
                        section=page.section_title,
                        is_table=True,
                        chunk_index=idx,
                    )
                )
                idx += 1

        # Prose body
        sents = _sentences(page.text or "")
        buf: list[str] = []
        buf_tokens = 0
        for s in sents:
            st = _tok_len(s)
            if buf_tokens + st > max_tokens and buf_tokens >= min_tokens:
                body = " ".join(buf)
                prefix = _prefix(project_name, page.section_title, page.page_num)
                chunks.append(
                    Chunk(
                        text=body,
                        prefixed_text=prefix + body,
                        token_count=_tok_len(body),
                        page_num=page.page_num,
                        section=page.section_title,
                        is_table=False,
                        chunk_index=idx,
                    )
                )
                idx += 1
                # overlap: keep last ~overlap tokens worth of sentences
                tail: list[str] = []
                tail_tokens = 0
                for prev in reversed(buf):
                    pt = _tok_len(prev)
                    if tail_tokens + pt > overlap:
                        break
                    tail.insert(0, prev)
                    tail_tokens += pt
                buf = tail + [s]
                buf_tokens = tail_tokens + st
            else:
                buf.append(s)
                buf_tokens += st
                if buf_tokens >= target:
                    body = " ".join(buf)
                    prefix = _prefix(project_name, page.section_title, page.page_num)
                    chunks.append(
                        Chunk(
                            text=body,
                            prefixed_text=prefix + body,
                            token_count=_tok_len(body),
                            page_num=page.page_num,
                            section=page.section_title,
                            is_table=False,
                            chunk_index=idx,
                        )
                    )
                    idx += 1
                    tail: list[str] = []
                    tail_tokens = 0
                    for prev in reversed(buf):
                        pt = _tok_len(prev)
                        if tail_tokens + pt > overlap:
                            break
                        tail.insert(0, prev)
                        tail_tokens += pt
                    buf = list(tail)
                    buf_tokens = tail_tokens

        if buf and sum(_tok_len(s) for s in buf) >= min_tokens:
            body = " ".join(buf)
            prefix = _prefix(project_name, page.section_title, page.page_num)
            chunks.append(
                Chunk(
                    text=body,
                    prefixed_text=prefix + body,
                    token_count=_tok_len(body),
                    page_num=page.page_num,
                    section=page.section_title,
                    is_table=False,
                    chunk_index=idx,
                )
            )
            idx += 1

    return chunks
