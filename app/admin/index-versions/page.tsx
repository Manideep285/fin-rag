"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type IV = {
  id: number;
  version: number;
  state: string;
  embedding_model: string;
  chunk_count: number | null;
  created_at: string;
  promoted_at: string | null;
};

const STATE_COLORS: Record<string, string> = {
  pending: "bg-zinc-200 text-zinc-700",
  building: "bg-amber-100 text-amber-800",
  ready: "bg-blue-100 text-blue-800",
  active: "bg-emerald-100 text-emerald-800",
  deprecated: "bg-zinc-200 text-zinc-700",
  purged: "bg-zinc-200 text-zinc-500",
};

export default function IndexVersionsPage() {
  const [versions, setVersions] = useState<IV[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setVersions(await api<IV[]>("/api/admin/index-versions"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
    }
  }
  useEffect(() => {
    void refresh();
  }, []);

  async function rebuild() {
    await api("/api/admin/index-versions/rebuild", { method: "POST" });
    await refresh();
  }
  async function promote(version: number) {
    await api("/api/admin/index-versions/promote", { method: "POST", json: { version } });
    await refresh();
  }
  async function rollback(version: number) {
    await api("/api/admin/index-versions/rollback", { method: "POST", json: { version } });
    await refresh();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Index versions</h1>
        <button
          onClick={rebuild}
          className="rounded-md bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 px-3 py-1.5 text-sm"
        >
          Rebuild index
        </button>
      </div>

      {error && <div className="text-sm text-red-600">{error}</div>}

      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-zinc-500 border-b border-zinc-200 dark:border-zinc-800">
          <tr>
            <th className="py-2 pr-4">Version</th>
            <th className="py-2 pr-4">State</th>
            <th className="py-2 pr-4">Model</th>
            <th className="py-2 pr-4">Chunks</th>
            <th className="py-2 pr-4">Created</th>
            <th className="py-2 pr-4">Promoted</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {versions.map((v) => (
            <tr key={v.id} className="border-b border-zinc-100 dark:border-zinc-900">
              <td className="py-2 pr-4 font-medium">v{v.version}</td>
              <td className="py-2 pr-4">
                <span className={`px-2 py-0.5 rounded text-xs ${STATE_COLORS[v.state] || "bg-zinc-100"}`}>
                  {v.state}
                </span>
              </td>
              <td className="py-2 pr-4 text-zinc-500 font-mono text-xs">{v.embedding_model}</td>
              <td className="py-2 pr-4">{v.chunk_count ?? "—"}</td>
              <td className="py-2 pr-4 text-zinc-500">{new Date(v.created_at).toLocaleString()}</td>
              <td className="py-2 pr-4 text-zinc-500">
                {v.promoted_at ? new Date(v.promoted_at).toLocaleString() : "—"}
              </td>
              <td className="py-2 text-right space-x-2">
                {v.state === "ready" && (
                  <button onClick={() => promote(v.version)} className="text-xs text-emerald-700 hover:underline">
                    Promote
                  </button>
                )}
                {v.state === "deprecated" && (
                  <button onClick={() => rollback(v.version)} className="text-xs text-blue-700 hover:underline">
                    Rollback to
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
