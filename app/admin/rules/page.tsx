"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Rule = {
  id: string;
  file_extension: string;
  max_file_size_mb: number;
  source_type: string;
  enabled: boolean;
};

export default function RulesPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [form, setForm] = useState({
    file_extension: ".pdf",
    max_file_size_mb: 50,
    source_type: "upload",
    enabled: true,
  });
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setRules(await api<Rule[]>("/api/admin/rules"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
    }
  }
  useEffect(() => {
    void refresh();
  }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api("/api/admin/rules", { method: "POST", json: form });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "add failed");
    }
  }

  async function del(id: string) {
    await api(`/api/admin/rules/${id}`, { method: "DELETE" });
    await refresh();
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Auto-approval rules</h1>
      <p className="text-sm text-zinc-500">
        Sources matching an enabled rule skip the manual approval queue.
      </p>

      <form
        onSubmit={add}
        className="grid grid-cols-1 md:grid-cols-5 gap-2 items-end p-4 rounded-xl border border-zinc-200 dark:border-zinc-800"
      >
        <Field label="Extension">
          <select
            value={form.file_extension}
            onChange={(e) => setForm({ ...form, file_extension: e.target.value })}
            className={inputCls}
          >
            {[".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md"].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </Field>
        <Field label="Max MB">
          <input
            type="number"
            min={1}
            value={form.max_file_size_mb}
            onChange={(e) => setForm({ ...form, max_file_size_mb: Number(e.target.value) })}
            className={inputCls}
          />
        </Field>
        <Field label="Source type">
          <select
            value={form.source_type}
            onChange={(e) => setForm({ ...form, source_type: e.target.value })}
            className={inputCls}
          >
            <option>upload</option>
            <option>sharepoint</option>
            <option>confluence</option>
          </select>
        </Field>
        <Field label="Enabled">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            className="h-5 w-5"
          />
        </Field>
        <button className="rounded-md bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 px-3 py-2 text-sm">
          Add rule
        </button>
      </form>

      {error && <div className="text-sm text-red-600">{error}</div>}

      <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
        {rules.map((r) => (
          <li key={r.id} className="py-3 flex items-center justify-between text-sm">
            <span>
              <code className="font-mono">{r.file_extension}</code> · {r.source_type} · ≤ {r.max_file_size_mb} MB
              {!r.enabled && <span className="ml-2 text-zinc-400">(disabled)</span>}
            </span>
            <button onClick={() => del(r.id)} className="text-xs text-red-700 hover:underline">
              Delete
            </button>
          </li>
        ))}
        {rules.length === 0 && <li className="py-3 text-sm text-zinc-500">No rules configured.</li>}
      </ul>

    </div>
  );
}

const inputCls =
  "w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-transparent px-3 py-2 text-sm";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-xs">
      <span className="block mb-1 text-zinc-500">{label}</span>
      {children}
    </label>
  );
}
