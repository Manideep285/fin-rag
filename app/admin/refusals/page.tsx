"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Row = {
  id: string;
  query_log_id: string;
  reason: string;
  created_at: string;
};

const REASON_COLORS: Record<string, string> = {
  guardrail: "bg-red-100 text-red-800",
  no_context: "bg-amber-100 text-amber-800",
  model_refusal: "bg-zinc-200 text-zinc-700",
};

export default function RefusalsPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Row[]>("/api/admin/refusal-logs?limit=200")
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : "load failed"));
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Refusals</h1>
      <p className="text-sm text-zinc-500">
        Recurring refusals point to gaps in the corpus or guardrail false positives.
      </p>

      {error && <div className="text-sm text-red-600">{error}</div>}

      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-zinc-500 border-b border-zinc-200 dark:border-zinc-800">
          <tr>
            <th className="py-2 pr-4">Query log</th>
            <th className="py-2 pr-4">Reason</th>
            <th className="py-2 pr-4">Created</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-zinc-100 dark:border-zinc-900">
              <td className="py-2 pr-4 font-mono text-xs">{r.query_log_id.slice(0, 8)}</td>
              <td className="py-2 pr-4">
                <span className={`px-2 py-0.5 rounded text-xs ${REASON_COLORS[r.reason] || "bg-zinc-100"}`}>
                  {r.reason}
                </span>
              </td>
              <td className="py-2 pr-4 text-zinc-500">{new Date(r.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
