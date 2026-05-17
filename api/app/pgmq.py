from __future__ import annotations
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def _qname(prefix: str, project_id) -> str:
    return f"{prefix}_{str(project_id).replace('-', '_')}"


def create_project_queues(db: Session, project_id) -> None:
    for prefix in ("ingest", "embed", "eval"):
        db.execute(text("SELECT pgmq.create(:q)"), {"q": _qname(prefix, project_id)})


def send(db: Session, prefix: str, project_id, payload: dict[str, Any]) -> int:
    msg_id = db.execute(
        text("SELECT pgmq.send(:q, :msg::jsonb)"),
        {"q": _qname(prefix, project_id), "msg": json.dumps(payload)},
    ).scalar_one()
    return int(msg_id)


def read(db: Session, prefix: str, project_id, vt_seconds: int = 60, batch: int = 1):
    rows = db.execute(
        text("SELECT * FROM pgmq.read(:q, :vt, :n)"),
        {"q": _qname(prefix, project_id), "vt": vt_seconds, "n": batch},
    ).mappings().all()
    return rows


def delete(db: Session, prefix: str, project_id, msg_id: int) -> None:
    db.execute(
        text("SELECT pgmq.delete(:q, :id)"),
        {"q": _qname(prefix, project_id), "id": msg_id},
    )
