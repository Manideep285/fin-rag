-- Extensions required by the platform.
-- pg_cron + pgmq must also be in shared_preload_libraries (see docker-compose).
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pgmq CASCADE;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Cron: clean expired rate-limit rows every 5 minutes.
SELECT cron.schedule(
  'cleanup-rate-limits',
  '*/5 * * * *',
  $$DELETE FROM rate_limits WHERE window_start < now() - interval '1 hour'$$
);

-- Cron: nightly pg_dump (requires the backup script + sidecar to actually copy
-- the file off the volume — see infra/scripts/backup-pg.sh).
-- This row is informational; the real backup is invoked by host cron / a sidecar.
