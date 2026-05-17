from __future__ import annotations
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import InviteKey, User, UserProjectRole

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# ---- password / key hashing ----

def hash_password(p: str) -> str:
    return pwd_ctx.hash(p)


def verify_password(p: str, h: str) -> bool:
    return pwd_ctx.verify(p, h)


def hash_invite_key(raw: str) -> str:
    return pwd_ctx.hash(raw)


def verify_invite_key(raw: str, h: str) -> bool:
    return pwd_ctx.verify(raw, h)


def generate_invite_key() -> str:
    # 256 bits, URL-safe.
    return f"finrag_{secrets.token_urlsafe(32)}"


# ---- jwt ----

def create_access_token(
    user_id: UUID, project_id: UUID, role: str, secret_version: int = 1
) -> tuple[str, int]:
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_ttl_hours)
    payload = {
        "sub": str(user_id),
        "pid": str(project_id),
        "role": role,
        "sv": secret_version,
        "exp": expires,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, settings.jwt_ttl_hours * 3600


# ---- dependency: current principal ----

class Principal:
    def __init__(self, user_id: UUID, project_id: UUID, role: str):
        self.user_id = user_id
        self.project_id = project_id
        self.role = role


def get_current_principal(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Principal:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {e}")
    return Principal(
        user_id=UUID(payload["sub"]),
        project_id=UUID(payload["pid"]),
        role=payload.get("role", "viewer"),
    )


def require_role(*allowed: str):
    def _dep(p: Principal = Depends(get_current_principal)) -> Principal:
        if p.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return p
    return _dep


# ---- invite key consumption ----

def consume_invite_key(db: Session, raw_key: str) -> InviteKey:
    """Look up + atomically consume an invite key. Raises 401/403 on failure."""
    # Bcrypt hashes are not deterministic — we must scan candidate rows.
    # Mitigation: keep an indexed prefix or maintain a separate HMAC lookup.
    # For pilot scale, scan non-revoked, non-expired keys.
    candidates = (
        db.query(InviteKey)
        .filter(
            InviteKey.revoked.is_(False),
            InviteKey.expires_at > datetime.now(timezone.utc),
            InviteKey.use_count < InviteKey.max_uses,
        )
        .all()
    )
    for k in candidates:
        if verify_invite_key(raw_key, k.key_hash):
            k.use_count += 1
            db.add(k)
            db.flush()
            return k
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or exhausted invite key")
