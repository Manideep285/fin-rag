# fin-rag — On-Prem RAG Platform (Pilot)

7-container monorepo implementing the architecture in `On-Prem RAG Platform — Updated Architecture Plan v2`.

## Layout

```
fin-rag/
  app/                  Next.js (chat UI + admin console)        → container: app
  components/           shared client components
  lib/                  browser-side helpers (API client, auth)
  api/                  FastAPI service                          → container: api
    app/                routers, services, models, auth
    alembic/            schema migrations
  worker/               Python worker (extract → chunk → embed,  → container: worker
                        plus HTTP /embed and /rerank endpoints,
                        plus async eval consumer)
  infra/                docker-compose, prometheus, grafana,
                        backup scripts, postgres init           → containers: db, store, llm, obs
  Makefile              convenience targets
  Dockerfile            Next.js app image
```

## Service map (§1)

| Container | What it runs |
|---|---|
| `app` | Next.js — chat + admin console |
| `api` | FastAPI — auth, ingest, query, admin |
| `db` | PostgreSQL with pgvector + pg_cron + pgmq |
| `store` | MinIO |
| `worker` | Extract / chunk / embed / async eval, exposes `/embed` + `/rerank` |
| `llm` | vLLM (GPU only) — skipped when `LLM_PROVIDER=openai` |
| `obs` | Grafana + Prometheus |

## First-run

1. **Decide the LLM lane** (Section 0 hardware gate).
   - GPU ≥ 12 GB VRAM → `LLM_PROVIDER=local`, then `make up-local`.
   - No GPU → `LLM_PROVIDER=openai`, set `LLM_BASE_URL` + `LLM_API_KEY` to any
     OpenAI-compatible endpoint (Azure, Bedrock, Groq, OpenRouter), then `make up`.
2. `cp infra/.env.example infra/.env` and fill in secrets.
3. `make up` (or `make up-local`).
4. `make migrate` to run Alembic.
5. Bootstrap an admin invite key:

   ```bash
   docker compose -f infra/docker-compose.yml exec api \
     python -m scripts.bootstrap_admin --project "Acme Pilot"
   ```

   Copy the printed key, visit `/signup`, and the resulting user becomes
   the project admin.

## Day-to-day

- `make logs` — tail everything.
- `make debug` — split-pane tail (requires tmux).
- `make psql` — open psql.
- `make backup` — run pg + minio backup scripts (RPO 24h, RTO 2h).

## App is the control center (§5)

- **User**: `/login`, `/signup` (invite-key gated), `/` (chat with citations + refusal styling), `/history` (per-user answer history).
- **Admin** (`/admin/*`): Overview, **Projects**, **Users & roles**, **Invite keys**, **Sources** (upload + approve/reject), **Auto-approval rules**, **Index versions** (rebuild / promote / rollback), **Observability** (live KPIs + embedded Grafana), **Evaluation**, **Refusals**.

The whole pilot — signup, ingestion approval, index promotion, query logs, refusals, eval — is driven from the Next.js admin console. Grafana is embedded inside `/admin/observability`; nothing requires switching tabs.

## LLM providers

The api speaks OpenAI's chat-completions wire format only. To switch providers,
change three env vars (no code changes):

| Provider | `LLM_BASE_URL` | `LLM_MODEL` example |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| OpenRouter | `https://openrouter.ai/api/v1` | `meta-llama/llama-3.1-70b-instruct` |
| Ollama (host) | `http://host.docker.internal:11434/v1` | `llama3.1:8b-instruct` |
| vLLM in-cluster | `http://llm:8001/v1` | `mistralai/Mistral-7B-Instruct-v0.2` |
| Azure OpenAI | `https://YOUR.openai.azure.com/openai/deployments/<deployment>/` | `<deployment>` |

See `infra/.env.example` for full recipes.

## Endpoints

- `http://localhost:3000` — Next.js (chat + `/admin`)
- `http://localhost:8000/health` — API health
- `http://localhost:8000/metrics` — Prometheus metrics for the API
- `http://localhost:9100/metrics` — Prometheus metrics for the worker
- `http://localhost:9001` — MinIO console
- `http://localhost:3001` — Grafana

## Auth model

Invite-key onboarding (§3). Keys are bcrypt-hashed, scoped to a project,
expire, and have `max_uses`. Signup rate-limited (5/10min/IP via PostgreSQL).
JWT issued post-verification; same payload shape will be issued by a future
`/auth/microsoft` route — downstream untouched.

> Pilot caveat: the browser stores the JWT in `localStorage`. Production
> should switch to `httpOnly` cookies set by a Next.js route handler that
> proxies `/auth/*` to the FastAPI backend.

## Retrieval (§8)

Hybrid: BM25 (Postgres `to_tsvector`) + pgvector cosine → Reciprocal Rank
Fusion (k=60) → cross-encoder rerank (`ms-marco-MiniLM-L-6-v2`) → token
budget. The api offloads embed and rerank to the worker over HTTP so the
api image stays free of torch.

## Index versioning (§14)

`pending → building → ready → active → deprecated → purged`. Promote and
rollback are atomic single-row updates on `projects.active_index_version`.
Deprecated versions are retained for the rollback window before purge.

## Multi-team namespace (§15)

- Postgres RLS policies isolate rows by `app.current_project_id` set per
  request. Workers run with `row_security = off`.
- MinIO uses `{project_id}/{source_id}/...` prefixes.
- pgmq queues are named `ingest_<pid>`, `embed_<pid>`, `eval_<pid>`.
- `POST /api/projects` performs full namespace onboarding in one call.

## Backups (§2)

- `infra/scripts/backup-pg.sh` — nightly `pg_dumpall` to `/backups/pg`
  with optional S3 mirror. Wire to host cron or a Dokploy schedule.
- `infra/scripts/backup-minio.sh` — `mc mirror` to `/backups/minio`.

## CI/CD (§13)

`.github/workflows/ci.yml` runs lint/test, builds and pushes the three
images, and triggers a Dokploy SSH deploy that runs `alembic upgrade head`
on container start. Configure these secrets in your repo:

`REGISTRY`, `REGISTRY_USER`, `REGISTRY_TOKEN`,
`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`.

## What is deferred to phase 2

- TruLens proper (the worker currently uses a token-overlap proxy for
  groundedness; swap in TruLens once the pilot proves value).
- Separate OpenTelemetry Collector — structured JSON logs are already
  OTEL-compatible; add an exporter without code changes.
- SharePoint / Confluence connectors.
- Streaming responses on `/api/query` (the LLM interface already supports
  `stream=true`; wire it through when needed).
