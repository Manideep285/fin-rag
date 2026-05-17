from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..auth import Principal, get_current_principal, require_role
from ..db import get_db
from ..models import AutoApprovalRule, Source
from ..pgmq import send as pgmq_send
from ..rate_limit import check_rate_limit
from ..schemas import SourceApprove, SourceOut
from ..storage import ensure_bucket, put_object, storage_key

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

ALLOWED_EXT = {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".csv"}


def _should_auto_approve(db: Session, project_id, ext: str, size_mb: float, source_type: str) -> bool:
    rules = (
        db.query(AutoApprovalRule)
        .filter(
            AutoApprovalRule.project_id == project_id,
            AutoApprovalRule.enabled.is_(True),
            AutoApprovalRule.file_extension == ext,
            AutoApprovalRule.source_type == source_type,
        )
        .all()
    )
    return any(size_mb <= r.max_file_size_mb for r in rules)


@router.post("/upload", response_model=SourceOut)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    check_rate_limit(request)
    if p.role not in ("contributor", "admin"):
        raise HTTPException(403, "contributor role required")

    name = file.filename or "unnamed"
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(415, f"unsupported extension {ext}")

    data = await file.read()
    size_mb = len(data) / 1024 / 1024

    source_id = uuid4()
    auto = _should_auto_approve(db, p.project_id, ext, size_mb, "upload")
    state = "approved" if auto else "pending"

    ensure_bucket()
    key = storage_key(p.project_id, source_id, f"original{ext}")
    put_object(key, data, content_type=file.content_type or "application/octet-stream")

    src = Source(
        id=source_id,
        project_id=p.project_id,
        name=name,
        source_type="upload",
        extension=ext,
        size_bytes=len(data),
        storage_key=key,
        state=state,
        auto_approved=auto,
        uploaded_by=p.user_id,
        metadata_={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(src)
    db.flush()

    if state == "approved":
        pgmq_send(db, "ingest", p.project_id, {"source_id": str(source_id)})

    db.commit()
    return SourceOut(
        id=src.id,
        project_id=src.project_id,
        name=src.name,
        source_type=src.source_type,
        extension=src.extension,
        size_bytes=src.size_bytes,
        state=src.state,
        auto_approved=src.auto_approved,
        created_at=src.created_at,
        error=src.error,
    )


@router.get("/sources", response_model=list[SourceOut])
def list_sources(p=Depends(get_current_principal), db: Session = Depends(get_db)):
    rows = (
        db.query(Source)
        .filter(Source.project_id == p.project_id)
        .order_by(Source.created_at.desc())
        .all()
    )
    return [
        SourceOut(
            id=r.id,
            project_id=r.project_id,
            name=r.name,
            source_type=r.source_type,
            extension=r.extension,
            size_bytes=r.size_bytes,
            state=r.state,
            auto_approved=r.auto_approved,
            created_at=r.created_at,
            error=r.error,
        )
        for r in rows
    ]


@router.post("/sources/{source_id}/approve", response_model=SourceOut)
def approve(
    source_id,
    body: SourceApprove,
    p=Depends(require_role("admin", "contributor")),
    db: Session = Depends(get_db),
):
    src = db.query(Source).filter(Source.id == source_id, Source.project_id == p.project_id).first()
    if not src:
        raise HTTPException(404, "source not found")
    if body.approve:
        src.state = "approved"
        pgmq_send(db, "ingest", p.project_id, {"source_id": str(src.id)})
    else:
        src.state = "rejected"
        src.error = body.reason
    src.updated_at = datetime.now(timezone.utc)
    db.commit()
    return SourceOut(
        id=src.id,
        project_id=src.project_id,
        name=src.name,
        source_type=src.source_type,
        extension=src.extension,
        size_bytes=src.size_bytes,
        state=src.state,
        auto_approved=src.auto_approved,
        created_at=src.created_at,
        error=src.error,
    )
