#!/usr/bin/env bash
# Nightly MinIO mirror. See plan §2.2.
set -euo pipefail

SRC=${SRC:-minio/rawfiles}
DST=${DST:-/backups/minio/rawfiles}
ALIAS=${MC_ALIAS:-minio}

# Configure mc alias once; idempotent.
mc alias set "$ALIAS" "${MINIO_URL:-http://store:9000}" \
  "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" >/dev/null

mc mirror --overwrite --remove "$SRC" "$DST"

echo "[backup-minio] mirrored $SRC -> $DST"
