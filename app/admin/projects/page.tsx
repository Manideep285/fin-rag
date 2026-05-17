"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthGuard";
import { api } from "@/lib/api";

type Project = {
  id: string;
  name: string;
  active_index_version: number | null;
};

export default function ProjectsPage() {
  const { principal } = useAuth();
  const [rows, setRows] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setRows(await api<Project[]>("/api/projects"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
    }
  }
  useEffect(() => {
    void refresh();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api("/api/projects", { method: "POST", json: { name: name.trim() } });
      setName("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "create failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Projects</h1>
      <p className="text-sm text-zinc-500">
        Each project is a fully-isolated namespace: own sources, chunks, queue, and access roles.
        After creating one, switch into it by signing up with an invite key scoped to that project.
      </p>

      <form
        onSubmit={create}
        className="flex gap-2 items-end p-4 rounded-xl border border-zinc-200 dark:border-zinc-800"
      >
        <label className="flex-1 text-xs">
          <span className="block mb-1 text-zinc-500">New project name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Acme Pilot"
            className="w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-transparent px-3 py-2 text-sm"
          />
        </label>
        <button
          disabled={busy || !name.trim()}
          className="rounded-md bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 px-3 py-2 text-sm font-medium disabled:opacity-40"
        >
          {busy ? "Creating…" : "Create"}
        </button>
      </form>

      {error && <div className="text-sm text-red-600">{error}</div>}

      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-zinc-500 border-b border-zinc-200 dark:border-zinc-800">
          <tr>
            <th className="py-2 pr-4">Name</th>
            <th className="py-2 pr-4">ID</th>
            <th className="py-2 pr-4">Active index</th>
            <th className="py-2 pr-4">Current</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-zinc-100 dark:border-zinc-900">
              <td className="py-2 pr-4 font-medium">{r.name}</td>
              <td className="py-2 pr-4 font-mono text-xs text-zinc-500">{r.id}</td>
              <td className="py-2 pr-4">{r.active_index_version ? `v${r.active_index_version}` : "—"}</td>
              <td className="py-2 pr-4">
                {principal?.project_id === r.id && (
                  <span className="text-xs text-emerald-700">signed in here</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
