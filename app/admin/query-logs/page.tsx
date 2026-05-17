"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Row = {
  id: string;
  query: string;
  answer: string | null;
  refused: boolean;
  latency_ms: number | null;
  num_chunks_used: number | null;
  created_at: string;
};

export default function QueryLogsPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState(100);

  async function refresh(l: number) {
    try {
      setRows(await api<Row[]>(`/api/admin/query-logs?limit=${l}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
    }
  }
  useEffect(() => {
    void refresh(limit);
  }, [limit]);

  const avgLatency = rows.length
    ? Math.round(
        rows.reduce((s, r) => s + (r.latency_ms || 0), 0) / rows.length,
      )
    : null;
  const refusedCount = rows.filter((r) => r.refused).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Query logs</h1>
          <p className="text-sm text-zinc-500 mt-1">
            All queries for this project, newest first. Includes latency, chunk
            usage, refusal status, and full answers.
          </p>
        </div>
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="rounded-md border border-zinc-300 dark:border-zinc-700 bg-transparent px-2 py-1 text-xs"
        >
          <option value={50}>Last 50</option>
          <option value={100}>Last 100</option>
          <option value={200}>Last 200</option>
          <option value={500}>Last 500</option>
        </select>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Stat label="Total shown" value={rows.length} />
        <Stat label="Refused" value={refusedCount} />
        <Stat
          label="Avg latency"
          value={avgLatency !== null ? `${avgLatency}ms` : "—"}
        />
      </div>

      {error && <div className="text-sm text-red-600">{error}</div>}

      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-zinc-500 border-b border-zinc-200 dark:border-zinc-800">
          <tr>
            <th className="py-2 pr-4">Time</th>
            <th className="py-2 pr-4">Query</th>
            <th className="py-2 pr-4">Latency</th>
            <th className="py-2 pr-4">Chunks</th>
            <th className="py-2 pr-4">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.id}
              className="border-b border-zinc-100 dark:border-zinc-900"
            >
              <td className="py-2 pr-4 text-zinc-500 text-xs whitespace-nowrap">
                {new Date(r.created_at).toLocaleString()}
              </td>
              <td className="py-2 pr-4">
                <details>
                  <summary className="cursor-pointer truncate max-w-[350px]">
                    {r.query}
                  </summary>
                  {r.answer && (
                    <div className="mt-2 text-sm whitespace-pre-wrap text-zinc-600 dark:text-zinc-400 bg-zinc-50 dark:bg-zinc-900 rounded p-3 border border-zinc-200 dark:border-zinc-800">
                      <div className="text-xs uppercase tracking-wide text-zinc-400 mb-1">
                        Answer
                      </div>
                      {r.answer}
                    </div>
                  )}
                </details>
              </td>
              <td className="py-2 pr-4 text-zinc-500">
                {r.latency_ms !== null ? `${r.latency_ms}ms` : "—"}
              </td>
              <td className="py-2 pr-4 text-zinc-500">
                {r.num_chunks_used ?? 0}
              </td>
              <td className="py-2 pr-4">
                {r.refused ? (
                  <span className="px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-800">
                    refused
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded text-xs bg-emerald-100 text-emerald-800">
                    ok
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Stat({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-4 bg-white dark:bg-zinc-950">
      <div className="text-xs uppercase tracking-wide text-zinc-500">
        {label}
      </div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}
