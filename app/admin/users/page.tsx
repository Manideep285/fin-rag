"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthGuard";
import { api } from "@/lib/api";

type Row = {
  user_id: string;
  email: string;
  display_name: string | null;
  role: "viewer" | "contributor" | "admin";
  created_at: string;
};

const ROLES: Row["role"][] = ["viewer", "contributor", "admin"];

export default function UsersPage() {
  const { principal } = useAuth();
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setRows(await api<Row[]>("/api/admin/users"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
    }
  }
  useEffect(() => {
    void refresh();
  }, []);

  async function setRole(user_id: string, role: Row["role"]) {
    try {
      await api(`/api/admin/users/${user_id}`, {
        method: "PATCH",
        json: { role },
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "update failed");
    }
  }

  async function remove(user_id: string) {
    if (!confirm("Remove this user from the project?")) return;
    try {
      await api(`/api/admin/users/${user_id}`, { method: "DELETE" });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "remove failed");
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Users & roles</h1>
      <p className="text-sm text-zinc-500">
        Membership in this project. To add a new user, generate an invite key on the
        Invite keys page and share it.
      </p>

      {error && <div className="text-sm text-red-600">{error}</div>}

      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-zinc-500 border-b border-zinc-200 dark:border-zinc-800">
          <tr>
            <th className="py-2 pr-4">Email</th>
            <th className="py-2 pr-4">Name</th>
            <th className="py-2 pr-4">Role</th>
            <th className="py-2 pr-4">Joined</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const isSelf = r.user_id === principal?.user_id;
            return (
              <tr key={r.user_id} className="border-b border-zinc-100 dark:border-zinc-900">
                <td className="py-2 pr-4">
                  {r.email}
                  {isSelf && <span className="ml-2 text-xs text-zinc-400">(you)</span>}
                </td>
                <td className="py-2 pr-4 text-zinc-500">{r.display_name || "—"}</td>
                <td className="py-2 pr-4">
                  <select
                    value={r.role}
                    disabled={isSelf}
                    onChange={(e) => setRole(r.user_id, e.target.value as Row["role"])}
                    className="rounded-md border border-zinc-300 dark:border-zinc-700 bg-transparent px-2 py-1 text-xs"
                  >
                    {ROLES.map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </td>
                <td className="py-2 pr-4 text-zinc-500">
                  {new Date(r.created_at).toLocaleDateString()}
                </td>
                <td className="py-2 text-right">
                  {!isSelf && (
                    <button
                      onClick={() => remove(r.user_id)}
                      className="text-xs text-red-700 hover:underline"
                    >
                      Remove
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
