from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..auth import (
    consume_invite_key,
    create_access_token,
    get_current_principal,
    hash_password,
    verify_password,
)
from ..db import get_db
from ..models import User, UserProjectRole
from ..rate_limit import check_rate_limit
from ..schemas import LoginRequest, SignupRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
def signup(req: SignupRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(request)
    invite = consume_invite_key(db, req.invite_key)

    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

    user = User(
        id=uuid4(),
        email=req.email,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
        secret_version=1,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.add(
        UserProjectRole(
            user_id=user.id, project_id=invite.project_scope, role=invite.role
        )
    )
    db.commit()

    token, ttl = create_access_token(user.id, invite.project_scope, invite.role, 1)
    return TokenResponse(access_token=token, expires_in=ttl)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(request)
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    role_row = (
        db.query(UserProjectRole).filter(UserProjectRole.user_id == user.id).first()
    )
    if not role_row:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "user has no project assignment")
    token, ttl = create_access_token(
        user.id, role_row.project_id, role_row.role, user.secret_version
    )
    return TokenResponse(access_token=token, expires_in=ttl)


@router.get("/me", response_model=UserOut)
def me(p=Depends(get_current_principal), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == p.user_id).first()
    if not user:
        raise HTTPException(404, "user not found")
    return UserOut(id=user.id, email=user.email, display_name=user.display_name)
