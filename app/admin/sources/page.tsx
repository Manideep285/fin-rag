"use client";
import { useEffect, useRef, useState } from "react";
import { API_BASE, ApiError, api, getToken } from "@/lib/api";

type Source = {
  id: string;
  name: string;
  source_type: string;
  extension: string;
  size_bytes: number;
  state: string;
  auto_approved: boolean;
  created_at: string;
  error: string | null;
};

const STATE_COLORS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  approved: "bg-blue-100 text-blue-800",
  extracting: "bg-blue-100 text-blue-800",
  extracted: "bg-blue-100 text-blue-800",
  chunked: "bg-blue-100 text-blue-800",
  embedded: "bg-emerald-100 text-emerald-800",
  rejected: "bg-zinc-200 text-zinc-700",
  failed: "bg-red-100 text-red-800",
};

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    try {
      setSources(await api<Source[]>("/api/ingest/sources"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
    }
  }
  useEffect(() => {
    void refresh();
  }, []);

  async function upload(file: File) {
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const tok = getToken();
      const res = await fetch(`${API_BASE}/api/ingest/upload`, {
        method: "POST",
        body: form,
        headers: tok ? { Authorization: `Bearer ${tok}` } : undefined,
      });
      if (!res.ok) throw new ApiError(res.status, `upload ${res.status}`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "upload failed");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function approve(id: string, ok: boolean) {
    try {
      await api(`/api/ingest/sources/${id}/approve`, {
        method: "POST",
        json: { approve: ok, reason: ok ? null : "rejected by admin" },
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "action failed");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Sources</h1>
        <label className="rounded-md bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 px-3 py-1.5 text-sm cursor-pointer">
          {busy ? "Uploading…" : "Upload file"}
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.xlsx,.pptx,.txt,.md,.csv"
            className="hidden"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void upload(f);
            }}
          />
        </label>
      </div>

      {error && <div className="text-sm text-red-600">{error}</div>}

      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-zinc-500 border-b border-zinc-200 dark:border-zinc-800">
          <tr>
            <th className="py-2 pr-4">Name</th>
            <th className="py-2 pr-4">Type</th>
            <th className="py-2 pr-4">Size</th>
            <th className="py-2 pr-4">State</th>
            <th className="py-2 pr-4">Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {sources.map((s) => (
            <tr key={s.id} className="border-b border-zinc-100 dark:border-zinc-900">
              <td className="py-2 pr-4 truncate max-w-[280px]" title={s.name}>{s.name}</td>
              <td className="py-2 pr-4 text-zinc-500">{s.extension}</td>
              <td className="py-2 pr-4 text-zinc-500">{(s.size_bytes / 1024).toFixed(0)} KB</td>
              <td className="py-2 pr-4">
                <span className={`px-2 py-0.5 rounded text-xs ${STATE_COLORS[s.state] || "bg-zinc-100 text-zinc-700"}`}>
                  {s.state}
                </span>
                {s.auto_approved && <span className="ml-1 text-xs text-zinc-400">auto</span>}
              </td>
              <td className="py-2 pr-4 text-zinc-500">{new Date(s.created_at).toLocaleString()}</td>
              <td className="py-2 text-right">
                {s.state === "pending" && (
                  <>
                    <button
                      onClick={() => approve(s.id, true)}
                      className="text-xs text-emerald-700 hover:underline mr-2"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => approve(s.id, false)}
                      className="text-xs text-red-700 hover:underline"
                    >
                      Reject
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
