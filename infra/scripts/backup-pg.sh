#!/usr/bin/env bash
# Nightly Postgres backup. Runs on host cron or as a Dokploy scheduled task.
# RPO target: 24h, RTO target: 2h (pilot).
set -euo pipefail

STAMP=$(date -u +%Y%m%d-%H%M%S)
OUTDIR=${OUTDIR:-/backups/pg}
RETAIN_DAYS=${RETAIN_DAYS:-30}
COMPOSE_FILE=${COMPOSE_FILE:-$(dirname "$0")/../docker-compose.yml}

mkdir -p "$OUTDIR"

docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_dumpall -U "${POSTGRES_USER:-finrag}" \
  | gzip > "$OUTDIR/pg-$STAMP.sql.gz"

# Optional: mirror to MinIO/S3
if [[ -n "${BACKUP_S3_TARGET:-}" ]]; then
  mc cp "$OUTDIR/pg-$STAMP.sql.gz" "$BACKUP_S3_TARGET/postgres/"
fi

# Retention
find "$OUTDIR" -name 'pg-*.sql.gz' -mtime +"$RETAIN_DAYS" -delete

echo "[backup-pg] wrote $OUTDIR/pg-$STAMP.sql.gz"
