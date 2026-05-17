"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Summary = {
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
};

export default function AdminOverview() {
  const [s, setS] = useState<Summary | null>(null);

  useEffect(() => {
    api<Summary>("/api/admin/summary").then(setS).catch(() => setS(null));
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Overview</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Users" value={s?.users_total ?? "—"} />
        <Stat
          label="Sources"
          value={s?.sources_total ?? "—"}
          hint={s ? `${s.sources_pending} pending approval` : ""}
        />
        <Stat
          label="Chunks indexed"
          value={s?.chunks_total ?? "—"}
          hint={s?.active_index_version ? `index v${s.active_index_version}` : "no active index"}
        />
        <Stat label="Queries (24h)" value={s?.queries_24h ?? "—"} />
        <Stat
          label="Refusal rate (24h)"
          value={s?.refusal_rate_24h === null || s?.refusal_rate_24h === undefined ? "—" : `${(s.refusal_rate_24h * 100).toFixed(1)}%`}
        />
        <Stat
          label="Latency p50 / p95 (24h)"
          value={
            s?.latency_ms_p50_24h !== null && s?.latency_ms_p50_24h !== undefined
              ? `${s.latency_ms_p50_24h} / ${s.latency_ms_p95_24h ?? "—"} ms`
              : "—"
          }
        />
        <Stat
          label="Avg groundedness"
          value={s?.avg_groundedness_24h === null || s?.avg_groundedness_24h === undefined ? "—" : s.avg_groundedness_24h.toFixed(2)}
        />
        <Stat
          label="Active index"
          value={s?.active_index_version ? `v${s.active_index_version}` : "none"}
        />
      </div>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Card title="Onboard a teammate" href="/admin/invite-keys" cta="Mint invite key">
          Generate a single-use invite key with a role and TTL. Share it; they sign up at /signup.
        </Card>
        <Card title="Add datasets" href="/admin/sources" cta="Upload">
          Drop in PDFs, DOCX, XLSX, PPTX, TXT, or MD. Auto-approval rules can skip the review step.
        </Card>
        <Card title="Promote new index" href="/admin/index-versions" cta="Manage versions">
          When a rebuild finishes, atomically promote it (and rollback if needed).
        </Card>
        <Card title="Watch the system" href="/admin/observability" cta="Open dashboard">
          Live KPIs and embedded Grafana for latency, refusal rate, and groundedness.
        </Card>
      </section>
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

function Card({
  title,
  href,
  cta,
  children,
}: {
  title: string;
  href: string;
  cta: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="block rounded-xl border border-zinc-200 dark:border-zinc-800 p-4 bg-white dark:bg-zinc-950 hover:border-zinc-400 dark:hover:border-zinc-600"
    >
      <div className="font-medium">{title}</div>
      <div className="text-sm text-zinc-500 mt-1">{children}</div>
      <div className="text-xs text-zinc-700 dark:text-zinc-300 mt-2 underline">{cta} →</div>
    </Link>
  );
}
