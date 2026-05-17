"use client";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
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

function HistoryInner() {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Row[]>("/api/me/queries?limit=100")
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : "load failed"));
  }, []);

  return (
    <main className="flex-1 mx-auto max-w-3xl w-full px-4 py-6 space-y-4">
      <h1 className="text-2xl font-semibold">My answer history</h1>
      {error && <div className="text-sm text-red-600">{error}</div>}
      {rows.length === 0 && (
        <div className="text-sm text-zinc-500">No questions yet.</div>
      )}
      <ul className="space-y-3">
        {rows.map((r) => (
          <li
            key={r.id}
            className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-4 bg-white dark:bg-zinc-950"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="font-medium text-sm flex-1">{r.query}</div>
              <div className="text-xs text-zinc-500 shrink-0">
                {new Date(r.created_at).toLocaleString()}
              </div>
            </div>
            {r.answer && (
              <details className="mt-2">
                <summary className="text-xs text-zinc-500 cursor-pointer">
                  {r.refused ? "Refused" : "Answer"} · {r.latency_ms ?? "?"}ms · {r.num_chunks_used ?? 0} chunks
                </summary>
                <div className="mt-2 text-sm whitespace-pre-wrap text-zinc-700 dark:text-zinc-300">
                  {r.answer}
                </div>
              </details>
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}

export default function HistoryPage() {
  return (
    <AuthGuard>
      <HistoryInner />
    </AuthGuard>
  );
}
