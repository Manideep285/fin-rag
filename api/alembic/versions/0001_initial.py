"""initial schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01

Implements the full pilot schema described in the architecture plan:
projects, users, invite_keys, user_project_roles, sources, auto_approval_rules,
chunks (pgvector + GIN tsvector), index_versions, query_logs, eval_results,
refusal_logs, rate_limits.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TIMESTAMPTZ = postgresql.TIMESTAMP(timezone=True)


def upgrade() -> None:
    # Extensions are normally created by the postgres init script.
    # Re-issue here so a fresh dev DB also works.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ---- projects -----------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("active_index_version", sa.Integer, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
    )

    # ---- users --------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text),
        sa.Column("secret_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
    )

    # ---- invite_keys --------------------------------------------------------
    op.create_table(
        "invite_keys",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key_hash", sa.Text, nullable=False, unique=True),
        sa.Column("role", sa.Text, nullable=False),  # viewer | contributor | admin
        sa.Column("project_scope", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", TIMESTAMPTZ, nullable=False),
        sa.Column("max_uses", sa.Integer, nullable=False, server_default="1"),
        sa.Column("use_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("revoked_at", TIMESTAMPTZ),
    )

    # ---- user_project_roles -------------------------------------------------
    op.create_table(
        "user_project_roles",
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.Text, nullable=False),
    )

    # ---- sources ------------------------------------------------------------
    op.create_table(
        "sources",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("source_type", sa.Text, nullable=False),  # upload | sharepoint | confluence
        sa.Column("extension", sa.Text, nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("state", sa.Text, nullable=False, server_default="pending"),
        # pending | approved | extracted | chunked | embedded | failed | rejected
        sa.Column("auto_approved", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("uploaded_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("error", sa.Text),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sources_project_state", "sources", ["project_id", "state"])

    # ---- auto_approval_rules ------------------------------------------------
    op.create_table(
        "auto_approval_rules",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_extension", sa.Text, nullable=False),
        sa.Column("max_file_size_mb", sa.Integer, nullable=False),
        sa.Column("source_type", sa.Text, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
    )

    # ---- index_versions -----------------------------------------------------
    op.create_table(
        "index_versions",
        sa.Column("id", sa.Integer, sa.Identity(always=True), primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("state", sa.Text, nullable=False, server_default="pending"),
        # pending | building | ready | active | deprecated | purged
        sa.Column("embedding_model", sa.Text, nullable=False),
        sa.Column("chunk_config", JSONB, nullable=False),
        sa.Column("source_ids", postgresql.ARRAY(UUID), nullable=False, server_default="{}"),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("promoted_at", TIMESTAMPTZ),
        sa.Column("deprecated_at", TIMESTAMPTZ),
        sa.Column("promoted_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.UniqueConstraint("project_id", "version", name="uq_index_version"),
    )

    # ---- chunks -------------------------------------------------------------
    op.create_table(
        "chunks",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", UUID, sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("index_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("prefixed_text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("page_num", sa.Integer),
        sa.Column("section", sa.Text),
        sa.Column("is_table", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("embedding", Vector(768)),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chunks_project_version", "chunks", ["project_id", "index_version"])
    op.create_index("ix_chunks_source", "chunks", ["source_id"])
    # Vector ANN index (cosine). Tune lists ~ sqrt(rowcount) once data lands.
    op.execute(
        "CREATE INDEX ix_chunks_embedding ON chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    # BM25 / FTS index
    op.execute(
        "CREATE INDEX ix_chunks_text_fts ON chunks "
        "USING gin(to_tsvector('english', text))"
    )

    # ---- query_logs ---------------------------------------------------------
    op.create_table(
        "query_logs",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("request_id", sa.Text, nullable=False),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("answer", sa.Text),
        sa.Column("chunk_ids", postgresql.ARRAY(UUID), server_default="{}"),
        sa.Column("context_token_count", sa.Integer),
        sa.Column("num_chunks_used", sa.Integer),
        sa.Column("llm_tokens_in", sa.Integer),
        sa.Column("llm_tokens_out", sa.Integer),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("status", sa.Integer),
        sa.Column("refused", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_query_logs_project_created", "query_logs", ["project_id", "created_at"])

    # ---- eval_results -------------------------------------------------------
    op.create_table(
        "eval_results",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("query_log_id", UUID, sa.ForeignKey("query_logs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("groundedness", sa.Float),
        sa.Column("answer_relevance", sa.Float),
        sa.Column("context_relevance", sa.Float),
        sa.Column("flagged", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
    )

    # ---- refusal_logs -------------------------------------------------------
    op.create_table(
        "refusal_logs",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("query_log_id", UUID, sa.ForeignKey("query_logs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),  # guardrail | no_context | model_refusal
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
    )

    # ---- rate_limits --------------------------------------------------------
    op.create_table(
        "rate_limits",
        sa.Column("ip", sa.Text, primary_key=True),
        sa.Column("endpoint", sa.Text, primary_key=True),
        sa.Column("window_start", TIMESTAMPTZ, primary_key=True),
        sa.Column("count", sa.Integer, nullable=False, server_default="1"),
    )

    # ---- pipeline_versions (Haystack-style versioned config) ---------------
    op.create_table(
        "pipeline_versions",
        sa.Column("id", sa.Integer, sa.Identity(always=True), primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("config_yaml", sa.Text, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "version", name="uq_pipeline_version"),
    )

    # ---- RLS (Row-Level Security) ------------------------------------------
    # API sets app.current_project_id per request. Workers run with elevated
    # role and bypass RLS via SET LOCAL row_security = off.
    for table in ("chunks", "sources", "query_logs", "eval_results", "refusal_logs"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_project_isolation ON {table}
            USING (
                current_setting('app.current_project_id', true) IS NULL
                OR current_setting('app.current_project_id', true) = ''
                OR project_id = current_setting('app.current_project_id', true)::uuid
            )
            """
        )


def downgrade() -> None:
    for table in (
        "pipeline_versions",
        "rate_limits",
        "refusal_logs",
        "eval_results",
        "query_logs",
        "chunks",
        "index_versions",
        "auto_approval_rules",
        "sources",
        "user_project_roles",
        "invite_keys",
        "users",
        "projects",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
