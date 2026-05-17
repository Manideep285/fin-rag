"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type EvalRow = {
  id: string;
  query_log_id: string;
  groundedness: number | null;
  answer_relevance: number | null;
  context_relevance: number | null;
  flagged: boolean;
  created_at: string;
};

export default function EvalPage() {
  const [rows, setRows] = useState<EvalRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<EvalRow[]>("/api/admin/eval-results?limit=200")
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : "load failed"));
  }, []);

  const flagged = rows.filter((r) => r.flagged).length;
  const avg = rows.length
    ? rows.reduce((s, r) => s + (r.groundedness || 0), 0) / rows.length
    : null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Evaluation results</h1>
      <p className="text-sm text-zinc-500">
        Async groundedness scoring. Sampled at {`{eval_sample_rate}`} of queries (configurable).
      </p>

      <div className="grid grid-cols-3 gap-3">
        <Stat label="Sampled" value={rows.length} />
        <Stat label="Flagged" value={flagged} />
        <Stat label="Avg groundedness" value={avg === null ? "—" : avg.toFixed(2)} />
      </div>

      {error && <div className="text-sm text-red-600">{error}</div>}

      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-zinc-500 border-b border-zinc-200 dark:border-zinc-800">
          <tr>
            <th className="py-2 pr-4">Query log</th>
            <th className="py-2 pr-4">Groundedness</th>
            <th className="py-2 pr-4">Flagged</th>
            <th className="py-2 pr-4">Created</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-zinc-100 dark:border-zinc-900">
              <td className="py-2 pr-4 font-mono text-xs">{r.query_log_id.slice(0, 8)}</td>
              <td className="py-2 pr-4">{r.groundedness?.toFixed(2) ?? "—"}</td>
              <td className="py-2 pr-4">
                {r.flagged ? <span className="text-red-700">yes</span> : <span className="text-zinc-500">no</span>}
              </td>
              <td className="py-2 pr-4 text-zinc-500">{new Date(r.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-4 bg-white dark:bg-zinc-950">
      <div className="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}
