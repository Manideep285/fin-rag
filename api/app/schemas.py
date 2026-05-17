from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ---- auth ----

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: Optional[str] = None
    invite_key: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    id: UUID
    email: str
    display_name: Optional[str]


# ---- projects ----

class ProjectCreate(BaseModel):
    name: str


class ProjectOut(BaseModel):
    id: UUID
    name: str
    active_index_version: Optional[int]


# ---- invite keys ----

class InviteKeyCreate(BaseModel):
    role: str = Field(pattern="^(viewer|contributor|admin)$")
    project_scope: UUID
    ttl_hours: int = 24 * 7
    max_uses: int = 1


class InviteKeyOut(BaseModel):
    id: UUID
    role: str
    project_scope: UUID
    expires_at: datetime
    max_uses: int
    use_count: int
    revoked: bool
    raw_key: Optional[str] = None  # only returned on creation


# ---- sources ----

class SourceOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    source_type: str
    extension: str
    size_bytes: int
    state: str
    auto_approved: bool
    created_at: datetime
    error: Optional[str]


class SourceApprove(BaseModel):
    approve: bool
    reason: Optional[str] = None


# ---- auto approval rules ----

class AutoApprovalRuleIn(BaseModel):
    file_extension: str
    max_file_size_mb: int
    source_type: str
    enabled: bool = True


class AutoApprovalRuleOut(AutoApprovalRuleIn):
    id: UUID
    project_id: UUID


# ---- index versions ----

class IndexVersionOut(BaseModel):
    id: int
    project_id: UUID
    version: int
    state: str
    embedding_model: str
    chunk_count: Optional[int]
    created_at: datetime
    promoted_at: Optional[datetime]


class IndexVersionPromote(BaseModel):
    version: int


# ---- query ----

class ChatMessage(BaseModel):
    role: str  # user | assistant | system
    content: str


class QueryRequest(BaseModel):
    project_id: UUID
    query: str
    conversation_history: list[ChatMessage] = []
    stream: bool = False


class CitationOut(BaseModel):
    chunk_id: UUID
    source_id: UUID
    source_name: str
    page_num: Optional[int]
    section: Optional[str]
    text: str
    score: float


class QueryResponse(BaseModel):
    request_id: str
    answer: str
    citations: list[CitationOut]
    refused: bool
    latency_ms: int
    context_tokens: int


# ---- eval / refusal ----

class EvalResultOut(BaseModel):
    id: UUID
    query_log_id: UUID
    groundedness: Optional[float]
    answer_relevance: Optional[float]
    context_relevance: Optional[float]
    flagged: bool
    created_at: datetime


class QueryLogOut(BaseModel):
    id: UUID
    query: str
    answer: Optional[str]
    refused: bool
    latency_ms: Optional[int]
    num_chunks_used: Optional[int]
    created_at: datetime
