"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/components/AuthGuard";

type Key = {
  id: string;
  role: string;
  expires_at: string;
  max_uses: number;
  use_count: number;
  revoked: boolean;
  raw_key?: string | null;
};

export default function InviteKeysPage() {
  const { principal } = useAuth();
  const [keys, setKeys] = useState<Key[]>([]);
  const [justCreated, setJustCreated] = useState<Key | null>(null);
  const [form, setForm] = useState({ role: "viewer", ttl_hours: 168, max_uses: 1 });
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setKeys(await api<Key[]>("/api/admin/invite-keys"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
    }
  }
  useEffect(() => {
    void refresh();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!principal) return;
    try {
      const k = await api<Key>("/api/admin/invite-keys", {
        method: "POST",
        json: { ...form, project_scope: principal.project_id },
      });
      setJustCreated(k);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "create failed");
    }
  }

  async function revoke(id: string) {
    await api(`/api/admin/invite-keys/${id}/revoke`, { method: "POST" });
    await refresh();
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Invite keys</h1>

      <form
        onSubmit={create}
        className="grid grid-cols-1 md:grid-cols-4 gap-2 items-end p-4 rounded-xl border border-zinc-200 dark:border-zinc-800"
      >
        <label className="text-xs">
          <span className="block mb-1 text-zinc-500">Role</span>
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            className="w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-transparent px-3 py-2 text-sm"
          >
            <option>viewer</option>
            <option>contributor</option>
            <option>admin</option>
          </select>
        </label>
        <label className="text-xs">
          <span className="block mb-1 text-zinc-500">TTL (hours)</span>
          <input
            type="number"
            min={1}
            value={form.ttl_hours}
            onChange={(e) => setForm({ ...form, ttl_hours: Number(e.target.value) })}
            className="w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-transparent px-3 py-2 text-sm"
          />
        </label>
        <label className="text-xs">
          <span className="block mb-1 text-zinc-500">Max uses</span>
          <input
            type="number"
            min={1}
            value={form.max_uses}
            onChange={(e) => setForm({ ...form, max_uses: Number(e.target.value) })}
            className="w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-transparent px-3 py-2 text-sm"
          />
        </label>
        <button className="rounded-md bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 px-3 py-2 text-sm">
          Generate
        </button>
      </form>

      {justCreated?.raw_key && (
        <div className="rounded-md border border-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 dark:border-emerald-800 p-3 text-sm">
          <div className="font-medium mb-1">Copy this key now — it will not be shown again.</div>
          <code className="block font-mono break-all bg-white dark:bg-zinc-900 p-2 rounded">
            {justCreated.raw_key}
          </code>
        </div>
      )}

      {error && <div className="text-sm text-red-600">{error}</div>}

      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-zinc-500 border-b border-zinc-200 dark:border-zinc-800">
          <tr>
            <th className="py-2 pr-4">ID</th>
            <th className="py-2 pr-4">Role</th>
            <th className="py-2 pr-4">Uses</th>
            <th className="py-2 pr-4">Expires</th>
            <th className="py-2 pr-4">Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => (
            <tr key={k.id} className="border-b border-zinc-100 dark:border-zinc-900">
              <td className="py-2 pr-4 font-mono text-xs">{k.id.slice(0, 8)}</td>
              <td className="py-2 pr-4">{k.role}</td>
              <td className="py-2 pr-4">{k.use_count} / {k.max_uses}</td>
              <td className="py-2 pr-4 text-zinc-500">{new Date(k.expires_at).toLocaleString()}</td>
              <td className="py-2 pr-4">
                {k.revoked ? <span className="text-red-700">revoked</span> : <span className="text-emerald-700">active</span>}
              </td>
              <td className="py-2 text-right">
                {!k.revoked && (
                  <button onClick={() => revoke(k.id)} className="text-xs text-red-700 hover:underline">
                    Revoke
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
