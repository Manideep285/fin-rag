from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ..auth import (
    Principal,
    generate_invite_key,
    hash_invite_key,
    require_role,
)
from ..config import settings
from ..db import get_db
from ..models import (
    AutoApprovalRule,
    EvalResult,
    IndexVersion,
    InviteKey,
    Project,
    QueryLog,
    RefusalLog,
    Source,
    User,
    UserProjectRole,
)
from ..pgmq import send as pgmq_send
from ..schemas import (
    AutoApprovalRuleIn,
    AutoApprovalRuleOut,
    IndexVersionOut,
    IndexVersionPromote,
    InviteKeyCreate,
    InviteKeyOut,
    QueryLogOut,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# -- invite keys --

@router.post("/invite-keys", response_model=InviteKeyOut)
def create_invite_key(
    body: InviteKeyCreate,
    p: Principal = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    if body.project_scope != p.project_id:
        raise HTTPException(403, "cannot mint keys outside your project")
    raw = generate_invite_key()
    k = InviteKey(
        id=uuid4(),
        key_hash=hash_invite_key(raw),
        role=body.role,
        project_scope=body.project_scope,
        created_by=p.user_id,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=body.ttl_hours),
        max_uses=body.max_uses,
        use_count=0,
        revoked=False,
    )
    db.add(k)
    db.commit()
    return InviteKeyOut(
        id=k.id,
        role=k.role,
        project_scope=k.project_scope,
        expires_at=k.expires_at,
        max_uses=k.max_uses,
        use_count=k.use_count,
        revoked=k.revoked,
        raw_key=raw,
    )


@router.get("/invite-keys", response_model=list[InviteKeyOut])
def list_invite_keys(p=Depends(require_role("admin")), db: Session = Depends(get_db)):
    rows = db.query(InviteKey).filter(InviteKey.project_scope == p.project_id).all()
    return [
        InviteKeyOut(
            id=r.id, role=r.role, project_scope=r.project_scope,
            expires_at=r.expires_at, max_uses=r.max_uses, use_count=r.use_count,
            revoked=r.revoked, raw_key=None,
        )
        for r in rows
    ]


@router.post("/invite-keys/{kid}/revoke")
def revoke_key(kid, p=Depends(require_role("admin")), db: Session = Depends(get_db)):
    k = db.query(InviteKey).filter(InviteKey.id == kid, InviteKey.project_scope == p.project_id).first()
    if not k:
        raise HTTPException(404, "key not found")
    k.revoked = True
    k.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


# -- auto-approval rules --

@router.get("/rules", response_model=list[AutoApprovalRuleOut])
def list_rules(p=Depends(require_role("admin")), db: Session = Depends(get_db)):
    rows = db.query(AutoApprovalRule).filter(AutoApprovalRule.project_id == p.project_id).all()
    return [
        AutoApprovalRuleOut(
            id=r.id, project_id=r.project_id, file_extension=r.file_extension,
            max_file_size_mb=r.max_file_size_mb, source_type=r.source_type, enabled=r.enabled,
        )
        for r in rows
    ]


@router.post("/rules", response_model=AutoApprovalRuleOut)
def add_rule(
    body: AutoApprovalRuleIn,
    p=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    r = AutoApprovalRule(
        id=uuid4(),
        project_id=p.project_id,
        file_extension=body.file_extension,
        max_file_size_mb=body.max_file_size_mb,
        source_type=body.source_type,
        enabled=body.enabled,
        created_at=datetime.now(timezone.utc),
    )
    db.add(r)
    db.commit()
    return AutoApprovalRuleOut(
        id=r.id, project_id=r.project_id, file_extension=r.file_extension,
        max_file_size_mb=r.max_file_size_mb, source_type=r.source_type, enabled=r.enabled,
    )


@router.delete("/rules/{rid}")
def delete_rule(rid, p=Depends(require_role("admin")), db: Session = Depends(get_db)):
    r = db.query(AutoApprovalRule).filter(AutoApprovalRule.id == rid, AutoApprovalRule.project_id == p.project_id).first()
    if not r:
        raise HTTPException(404)
    db.delete(r)
    db.commit()
    return {"ok": True}


# -- index versions --

@router.get("/index-versions", response_model=list[IndexVersionOut])
def list_versions(p=Depends(require_role("admin")), db: Session = Depends(get_db)):
    rows = (
        db.query(IndexVersion)
        .filter(IndexVersion.project_id == p.project_id)
        .order_by(IndexVersion.version.desc())
        .all()
    )
    return [
        IndexVersionOut(
            id=r.id, project_id=r.project_id, version=r.version, state=r.state,
            embedding_model=r.embedding_model, chunk_count=r.chunk_count,
            created_at=r.created_at, promoted_at=r.promoted_at,
        )
        for r in rows
    ]


@router.post("/index-versions/rebuild", response_model=IndexVersionOut)
def rebuild_index(p=Depends(require_role("admin")), db: Session = Depends(get_db)):
    last = (
        db.query(func.max(IndexVersion.version))
        .filter(IndexVersion.project_id == p.project_id)
        .scalar()
    ) or 0
    iv = IndexVersion(
        project_id=p.project_id,
        version=last + 1,
        state="building",
        embedding_model=settings.embed_model,
        chunk_config={
            "target_tokens": settings.chunk_target_tokens,
            "max_tokens": settings.chunk_max_tokens,
            "overlap_tokens": settings.chunk_overlap_tokens,
            "min_chunk_tokens": settings.chunk_min_tokens,
        },
        source_ids=[],
        chunk_count=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(iv)
    db.flush()
    pgmq_send(db, "ingest", p.project_id, {"rebuild_index_version": iv.version})
    db.commit()
    return IndexVersionOut(
        id=iv.id, project_id=iv.project_id, version=iv.version, state=iv.state,
        embedding_model=iv.embedding_model, chunk_count=iv.chunk_count,
        created_at=iv.created_at, promoted_at=iv.promoted_at,
    )


@router.post("/index-versions/promote")
def promote_version(
    body: IndexVersionPromote,
    p=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    iv = (
        db.query(IndexVersion)
        .filter(IndexVersion.project_id == p.project_id, IndexVersion.version == body.version)
        .first()
    )
    if not iv:
        raise HTTPException(404, "version not found")
    if iv.state not in ("ready", "active"):
        raise HTTPException(409, f"version is {iv.state}, must be ready")

    # Deprecate old active version
    db.query(IndexVersion).filter(
        IndexVersion.project_id == p.project_id,
        IndexVersion.state == "active",
    ).update({"state": "deprecated", "deprecated_at": datetime.now(timezone.utc)})

    iv.state = "active"
    iv.promoted_at = datetime.now(timezone.utc)
    iv.promoted_by = p.user_id

    db.query(Project).filter(Project.id == p.project_id).update(
        {"active_index_version": iv.version}
    )
    db.commit()
    return {"ok": True, "active_version": iv.version}


@router.post("/index-versions/rollback")
def rollback_version(
    body: IndexVersionPromote,
    p=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    iv = (
        db.query(IndexVersion)
        .filter(IndexVersion.project_id == p.project_id, IndexVersion.version == body.version)
        .first()
    )
    if not iv or iv.state == "purged":
        raise HTTPException(404, "version not found or purged")
    db.query(Project).filter(Project.id == p.project_id).update(
        {"active_index_version": iv.version}
    )
    iv.state = "active"
    db.commit()
    return {"ok": True, "active_version": iv.version}


# -- query logs / eval / refusal --

@router.get("/query-logs", response_model=list[QueryLogOut])
def query_logs(
    limit: int = 50,
    p=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(QueryLog)
        .filter(QueryLog.project_id == p.project_id)
        .order_by(QueryLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        QueryLogOut(
            id=r.id, query=r.query, answer=r.answer, refused=r.refused,
            latency_ms=r.latency_ms, num_chunks_used=r.num_chunks_used,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/refusal-logs")
def refusal_logs(
    limit: int = 50, p=Depends(require_role("admin")), db: Session = Depends(get_db)
):
    rows = (
        db.query(RefusalLog)
        .filter(RefusalLog.project_id == p.project_id)
        .order_by(RefusalLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {"id": str(r.id), "query_log_id": str(r.query_log_id),
         "reason": r.reason, "created_at": r.created_at.isoformat()}
        for r in rows
    ]


@router.get("/eval-results")
def eval_results(
    limit: int = 50, p=Depends(require_role("admin")), db: Session = Depends(get_db)
):
    rows = (
        db.query(EvalResult)
        .filter(EvalResult.project_id == p.project_id)
        .order_by(EvalResult.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(r.id),
            "query_log_id": str(r.query_log_id),
            "groundedness": r.groundedness,
            "answer_relevance": r.answer_relevance,
            "context_relevance": r.context_relevance,
            "flagged": r.flagged,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


# -- users / roles --

@router.get("/users")
def list_users(p=Depends(require_role("admin")), db: Session = Depends(get_db)):
    rows = (
        db.query(User, UserProjectRole)
        .join(UserProjectRole, UserProjectRole.user_id == User.id)
        .filter(UserProjectRole.project_id == p.project_id)
        .order_by(User.created_at.desc())
        .all()
    )
    return [
        {
            "user_id": str(u.id),
            "email": u.email,
            "display_name": u.display_name,
            "role": r.role,
            "created_at": u.created_at.isoformat(),
        }
        for (u, r) in rows
    ]


@router.patch("/users/{user_id}")
def update_user_role(
    user_id,
    body: dict,
    p=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    new_role = (body or {}).get("role")
    if new_role not in ("viewer", "contributor", "admin"):
        raise HTTPException(400, "role must be viewer|contributor|admin")
    if str(user_id) == str(p.user_id) and new_role != "admin":
        raise HTTPException(409, "cannot demote yourself")
    upr = (
        db.query(UserProjectRole)
        .filter(
            UserProjectRole.user_id == user_id,
            UserProjectRole.project_id == p.project_id,
        )
        .first()
    )
    if not upr:
        raise HTTPException(404, "user is not a member of this project")
    upr.role = new_role
    # Bump secret_version so the user's existing JWT becomes stale on the
    # next refresh path you wire up. The JWT itself stays valid until exp.
    db.query(User).filter(User.id == user_id).update(
        {"secret_version": User.secret_version + 1}
    )
    db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}")
def remove_user(user_id, p=Depends(require_role("admin")), db: Session = Depends(get_db)):
    if str(user_id) == str(p.user_id):
        raise HTTPException(409, "cannot remove yourself")
    deleted = (
        db.query(UserProjectRole)
        .filter(
            UserProjectRole.user_id == user_id,
            UserProjectRole.project_id == p.project_id,
        )
        .delete()
    )
    db.commit()
    if not deleted:
        raise HTTPException(404, "user not in project")
    return {"ok": True}


# -- summary stats for the admin overview / observability page --

@router.get("/summary")
def summary(p=Depends(require_role("admin")), db: Session = Depends(get_db)):
    pid = p.project_id

    sources_total = (
        db.query(func.count(Source.id)).filter(Source.project_id == pid).scalar() or 0
    )
    sources_pending = (
        db.query(func.count(Source.id))
        .filter(Source.project_id == pid, Source.state == "pending")
        .scalar()
        or 0
    )
    chunks_total = db.execute(
        text("SELECT count(*) FROM chunks WHERE project_id = :pid"),
        {"pid": str(pid)},
    ).scalar_one()

    active_iv = (
        db.query(IndexVersion)
        .filter(IndexVersion.project_id == pid, IndexVersion.state == "active")
        .first()
    )

    queries_24h = db.execute(
        text(
            "SELECT count(*) FROM query_logs "
            "WHERE project_id = :pid AND created_at > now() - interval '24 hours'"
        ),
        {"pid": str(pid)},
    ).scalar_one()
    refused_24h = db.execute(
        text(
            "SELECT count(*) FROM query_logs "
            "WHERE project_id = :pid AND refused = true "
            "AND created_at > now() - interval '24 hours'"
        ),
        {"pid": str(pid)},
    ).scalar_one()
    p50_24h = db.execute(
        text(
            "SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY latency_ms) "
            "FROM query_logs WHERE project_id = :pid "
            "AND created_at > now() - interval '24 hours'"
        ),
        {"pid": str(pid)},
    ).scalar()
    p95_24h = db.execute(
        text(
            "SELECT percentile_disc(0.95) WITHIN GROUP (ORDER BY latency_ms) "
            "FROM query_logs WHERE project_id = :pid "
            "AND created_at > now() - interval '24 hours'"
        ),
        {"pid": str(pid)},
    ).scalar()
    avg_groundedness_24h = db.execute(
        text(
            "SELECT avg(groundedness) FROM eval_results "
            "WHERE project_id = :pid "
            "AND created_at > now() - interval '24 hours'"
        ),
        {"pid": str(pid)},
    ).scalar()
    flagged_24h = db.execute(
        text(
            "SELECT count(*) FROM eval_results "
            "WHERE project_id = :pid AND flagged = true "
            "AND created_at > now() - interval '24 hours'"
        ),
        {"pid": str(pid)},
    ).scalar_one()

    users_total = (
        db.query(func.count(UserProjectRole.user_id))
        .filter(UserProjectRole.project_id == pid)
        .scalar()
        or 0
    )

    return {
        "project_id": str(pid),
        "users_total": users_total,
        "sources_total": sources_total,
        "sources_pending": sources_pending,
        "chunks_total": int(chunks_total or 0),
        "active_index_version": active_iv.version if active_iv else None,
        "queries_24h": int(queries_24h or 0),
        "refused_24h": int(refused_24h or 0),
        "refusal_rate_24h": (
            float(refused_24h) / float(queries_24h) if queries_24h else None
        ),
        "latency_ms_p50_24h": int(p50_24h) if p50_24h is not None else None,
        "latency_ms_p95_24h": int(p95_24h) if p95_24h is not None else None,
        "avg_groundedness_24h": (
            float(avg_groundedness_24h) if avg_groundedness_24h is not None else None
        ),
        "eval_flagged_24h": int(flagged_24h or 0),
    }
