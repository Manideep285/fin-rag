"""Job handlers: ingest, embed, eval (§16 data flow)."""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import text

from .chunking import chunk_document
from .config import settings
from .db import session_scope
from .embedder import embed_texts
from .extractors import route as route_extractor
from .storage import get_bytes, put_bytes


def _set_state(db, source_id: UUID, state: str, error: str | None = None) -> None:
    db.execute(
        text(
            "UPDATE sources SET state=:s, error=:e, updated_at=now() WHERE id=:id"
        ),
        {"s": state, "e": error, "id": str(source_id)},
    )


def _project_info(db, project_id: UUID) -> tuple[str, int]:
    row = db.execute(
        text("SELECT name, COALESCE(active_index_version,1) AS v FROM projects WHERE id=:id"),
        {"id": str(project_id)},
    ).mappings().one()
    return row["name"], int(row["v"])


def handle_ingest(payload: dict) -> None:
    source_id = UUID(payload["source_id"])
    with session_scope() as db:
        src = db.execute(
            text(
                "SELECT id, project_id, name, extension, storage_key FROM sources WHERE id=:id"
            ),
            {"id": str(source_id)},
        ).mappings().one()
        project_name, active_version = _project_info(db, src["project_id"])

        try:
            _set_state(db, source_id, "extracting")
            db.commit()
            raw = get_bytes(src["storage_key"])
            extractor = route_extractor(src["extension"])
            doc = extractor(str(source_id), raw)

            # Persist normalized JSON next to original
            extracted_key = src["storage_key"].rsplit("/", 1)[0] + "/extracted.json"
            put_bytes(
                extracted_key,
                json.dumps(
                    {
                        "source_id": str(source_id),
                        "pages": [
                            {
                                "page_num": p.page_num,
                                "text": p.text,
                                "tables": p.tables,
                                "section_title": p.section_title,
                                "is_table": p.is_table,
                            }
                            for p in doc.pages
                        ],
                    }
                ).encode("utf-8"),
                content_type="application/json",
            )
            _set_state(db, source_id, "extracted")
            db.commit()

            # Chunking
            chunks = chunk_document(doc, project_name)
            now = datetime.now(timezone.utc)
            for c in chunks:
                db.execute(
                    text(
                        """
                        INSERT INTO chunks (id, source_id, project_id, index_version,
                            chunk_index, text, prefixed_text, token_count, page_num,
                            section, is_table, metadata, embedding, created_at)
                        VALUES (:id, :sid, :pid, :iv, :ci, :tx, :pt, :tc, :pg, :sec,
                            :it, '{}'::jsonb, NULL, :ts)
                        """
                    ),
                    {
                        "id": str(uuid4()),
                        "sid": str(source_id),
                        "pid": str(src["project_id"]),
                        "iv": active_version,
                        "ci": c.chunk_index,
                        "tx": c.text,
                        "pt": c.prefixed_text,
                        "tc": c.token_count,
                        "pg": c.page_num,
                        "sec": c.section,
                        "it": c.is_table,
                        "ts": now,
                    },
                )
            _set_state(db, source_id, "chunked")
            db.commit()

            # Enqueue embedding
            db.execute(
                text(
                    "SELECT pgmq.send(:q, :msg::jsonb)"
                ),
                {
                    "q": f"embed_{str(src['project_id']).replace('-', '_')}",
                    "msg": json.dumps({"source_id": str(source_id)}),
                },
            )
        except Exception as e:
            _set_state(db, source_id, "failed", error=str(e)[:500])
            raise


def handle_embed(payload: dict) -> None:
    source_id = UUID(payload["source_id"])
    with session_scope() as db:
        rows = db.execute(
            text(
                "SELECT id, prefixed_text FROM chunks "
                "WHERE source_id=:sid AND embedding IS NULL ORDER BY chunk_index"
            ),
            {"sid": str(source_id)},
        ).mappings().all()
        if not rows:
            _set_state(db, source_id, "embedded")
            return

        BATCH = 64
        for i in range(0, len(rows), BATCH):
            batch = rows[i : i + BATCH]
            embs = embed_texts([r["prefixed_text"] for r in batch])
            for r, e in zip(batch, embs):
                db.execute(
                    text("UPDATE chunks SET embedding = CAST(:e AS vector) WHERE id=:id"),
                    {"e": str(e), "id": str(r["id"])},
                )
            db.commit()

        _set_state(db, source_id, "embedded")

        # If all approved sources for this project's active index_version are
        # embedded, mark IndexVersion ready.
        db.execute(
            text(
                """
                UPDATE index_versions iv
                   SET state='ready', chunk_count = (
                     SELECT count(*) FROM chunks
                     WHERE project_id = iv.project_id
                       AND index_version = iv.version
                   )
                 WHERE iv.project_id = (SELECT project_id FROM sources WHERE id=:sid)
                   AND iv.state = 'building'
                   AND NOT EXISTS (
                     SELECT 1 FROM sources s
                     WHERE s.project_id = iv.project_id
                       AND s.state IN ('approved','extracting','extracted','chunked')
                   )
                """
            ),
            {"sid": str(source_id)},
        )


def handle_eval(payload: dict) -> None:
    """Async TruLens-style eval. For pilot: a thin scorer that compares the
    answer against the retrieved context using the LLM as judge. Real
    TruLens hookup goes here when the pilot proves value (§11)."""
    from uuid import uuid4

    query_log_id = UUID(payload["query_log_id"])
    with session_scope() as db:
        row = db.execute(
            text(
                """
                SELECT ql.id, ql.project_id, ql.query, ql.answer, ql.chunk_ids
                FROM query_logs ql WHERE ql.id=:id
                """
            ),
            {"id": str(query_log_id)},
        ).mappings().one_or_none()
        if not row or not row["answer"]:
            return

        # Pilot stand-in: token-overlap proxy for groundedness.
        chunks = db.execute(
            text("SELECT text FROM chunks WHERE id = ANY(:ids)"),
            {"ids": list(row["chunk_ids"] or [])},
        ).scalars().all()
        ctx_text = " ".join(chunks).lower().split()
        ans_words = (row["answer"] or "").lower().split()
        if not ans_words:
            grounded = 0.0
        else:
            ctx_set = set(ctx_text)
            grounded = sum(1 for w in ans_words if w in ctx_set) / len(ans_words)

        flagged = grounded < 0.6
        db.execute(
            text(
                """
                INSERT INTO eval_results (id, query_log_id, project_id,
                    groundedness, answer_relevance, context_relevance,
                    flagged, notes, created_at)
                VALUES (:id, :qid, :pid, :g, NULL, NULL, :f, :n, now())
                """
            ),
            {
                "id": str(uuid4()),
                "qid": str(query_log_id),
                "pid": str(row["project_id"]),
                "g": grounded,
                "f": flagged,
                "n": "pilot token-overlap proxy",
            },
        )
