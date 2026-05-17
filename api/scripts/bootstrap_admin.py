"""Bootstrap a first admin invite key for a brand-new database.

Usage (inside the api container):

    python -m scripts.bootstrap_admin --project "Acme Pilot"

Prints a one-time invite key to stdout. Use it to sign up at /signup; the
resulting user becomes the admin of that project.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.auth import generate_invite_key, hash_invite_key
from app.config import settings
from app.db import session_scope
from app.models import IndexVersion, InviteKey, Project
from app.pgmq import create_project_queues


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="project name")
    ap.add_argument("--ttl-hours", type=int, default=24)
    ap.add_argument("--max-uses", type=int, default=1)
    args = ap.parse_args()

    with session_scope() as db:
        project = db.query(Project).filter(Project.name == args.project).first()
        if not project:
            project = Project(
                id=uuid4(),
                name=args.project,
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
            create_project_queues(db, project.id)

        raw = generate_invite_key()
        db.add(
            InviteKey(
                id=uuid4(),
                key_hash=hash_invite_key(raw),
                role="admin",
                project_scope=project.id,
                created_by=None,
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=args.ttl_hours),
                max_uses=args.max_uses,
                use_count=0,
                revoked=False,
            )
        )

    print("=" * 60)
    print(f"Project   : {args.project}")
    print(f"Project ID: {project.id}")
    print(f"Role      : admin")
    print(f"Invite key: {raw}")
    print(f"Expires   : in {args.ttl_hours}h, max_uses={args.max_uses}")
    print("=" * 60)
    print("Sign up at /signup with this key to become the project admin.")


if __name__ == "__main__":
    main()
