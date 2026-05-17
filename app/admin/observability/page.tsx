"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthGuard";
import { api } from "@/lib/api";

type Summary = {
  project_id: string;
  users_total: number;
  sources_total: number;
  sources_pending: number;
  chunks_total: number;
  active_index_version: number | null;
  queries_24h: number;
  refused_24h: number;
  refusal_rate_24h: number | null;
  latency_ms_p50_24h: number | null;
  latency_ms_p95_24h: number | null;
  avg_groundedness_24h: number | null;
  eval_flagged_24h: number;
};

const GRAFANA_BASE =
  process.env.NEXT_PUBLIC_GRAFANA_BASE_URL || "http://localhost:3001";
const DASHBOARD_UID = "fin-rag-project";

export default function ObservabilityPage() {
  const { principal } = useAuth();
  const [s, setS] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const tick = () =>
      api<Summary>("/api/admin/summary")
        .then(setS)
        .catch((e) => setError(e instanceof Error ? e.message : "load failed"));
    tick();
    const t = setInterval(tick, 15_000);
    return () => clearInterval(t);
  }, []);

  const dashboardUrl = principal
    ? `${GRAFANA_BASE}/d/${DASHBOARD_UID}/fin-rag-project?orgId=1&kiosk=tv&theme=light&var-project_id=${principal.project_id}`
    : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Observability</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Live KPIs for the last 24 hours. Full Grafana dashboard embedded below pulls metrics
          from Prometheus and structured logs from the database.
        </p>
      </div>

      {error && <div className="text-sm text-red-600">{error}</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Users" value={s?.users_total ?? "—"} />
        <Stat label="Sources" value={s?.sources_total ?? "—"} hint={s ? `${s.sources_pending} pending` : ""} />
        <Stat label="Chunks" value={s?.chunks_total ?? "—"} hint={s?.active_index_version ? `index v${s.active_index_version}` : "no active index"} />
        <Stat label="Queries (24h)" value={s?.queries_24h ?? "—"} />
        <Stat
          label="Refusal rate (24h)"
          value={s?.refusal_rate_24h === null || s?.refusal_rate_24h === undefined ? "—" : `${(s.refusal_rate_24h * 100).toFixed(1)}%`}
          hint={s ? `${s.refused_24h} refused` : ""}
        />
        <Stat
          label="Latency p50 (24h)"
          value={s?.latency_ms_p50_24h === null || s?.latency_ms_p50_24h === undefined ? "—" : `${s.latency_ms_p50_24h}ms`}
        />
        <Stat
          label="Latency p95 (24h)"
          value={s?.latency_ms_p95_24h === null || s?.latency_ms_p95_24h === undefined ? "—" : `${s.latency_ms_p95_24h}ms`}
        />
        <Stat
          label="Avg groundedness (24h)"
          value={s?.avg_groundedness_24h === null || s?.avg_groundedness_24h === undefined ? "—" : s.avg_groundedness_24h.toFixed(2)}
          hint={s ? `${s.eval_flagged_24h} flagged` : ""}
        />
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold">Grafana — project dashboard</h2>
          {dashboardUrl && (
            <a
              href={dashboardUrl.replace("&kiosk=tv", "")}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs underline text-zinc-600 dark:text-zinc-300"
            >
              Open in Grafana ↗
            </a>
          )}
        </div>
        {dashboardUrl ? (
          <iframe
            title="Grafana project dashboard"
            src={dashboardUrl}
            className="w-full h-[900px] rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white"
          />
        ) : (
          <div className="text-sm text-zinc-500">Sign in to view the dashboard.</div>
        )}
        <p className="text-xs text-zinc-500 mt-2">
          The iframe requires Grafana to allow embedding. Grafana&apos;s docker image in
          this repo is configured with <code>GF_SECURITY_ALLOW_EMBEDDING=true</code> and
          anonymous viewer mode for the pilot. Replace with proxy auth for production.
        </p>
      </div>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-4 bg-white dark:bg-zinc-950">
      <div className="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
      {hint && <div className="text-xs text-zinc-500 mt-1">{hint}</div>}
    </div>
  );
}
