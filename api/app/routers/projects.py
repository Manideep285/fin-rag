from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_principal, require_role
from ..config import settings
from ..db import get_db
from ..models import IndexVersion, Project, UserProjectRole
from ..pgmq import create_project_queues
from ..schemas import ProjectCreate, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(
    body: ProjectCreate,
    p=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    if db.query(Project).filter(Project.name == body.name).first():
        raise HTTPException(409, "project name already taken")
    project = Project(
        id=uuid4(),
        name=body.name,
        active_index_version=None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(project)
    db.flush()

    db.add(
        IndexVersion(
            project_id=project.id,
            version=1,
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
    )
    db.add(UserProjectRole(user_id=p.user_id, project_id=project.id, role="admin"))

    create_project_queues(db, project.id)
    db.commit()
    return ProjectOut(id=project.id, name=project.name, active_index_version=None)


@router.get("", response_model=list[ProjectOut])
def list_projects(p=Depends(get_current_principal), db: Session = Depends(get_db)):
    rows = (
        db.query(Project)
        .join(UserProjectRole, UserProjectRole.project_id == Project.id)
        .filter(UserProjectRole.user_id == p.user_id)
        .all()
    )
    return [
        ProjectOut(id=r.id, name=r.name, active_index_version=r.active_index_version)
        for r in rows
    ]
