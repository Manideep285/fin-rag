"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { signup } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "", display_name: "", invite_key: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function set<K extends keyof typeof form>(k: K, v: string) {
    setForm({ ...form, [k]: v });
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await signup(form);
      router.replace("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "signup failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex-1 flex items-center justify-center px-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-4 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-6 bg-white dark:bg-zinc-950"
      >
        <h1 className="text-xl font-semibold">Create account</h1>
        {(["email", "password", "display_name", "invite_key"] as const).map((k) => (
          <div key={k}>
            <label className="block text-sm mb-1 capitalize">{k.replace("_", " ")}</label>
            <input
              type={k === "password" ? "password" : k === "email" ? "email" : "text"}
              required={k !== "display_name"}
              value={form[k]}
              onChange={(e) => set(k, e.target.value)}
              className="w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-transparent px-3 py-2 text-sm font-mono"
            />
          </div>
        ))}
        {error && <div className="text-sm text-red-600">{error}</div>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 py-2 text-sm font-medium disabled:opacity-40"
        >
          {busy ? "Creating…" : "Create account"}
        </button>
        <div className="text-sm text-zinc-500 text-center">
          Already have an account?{" "}
          <Link href="/login" className="underline">
            Sign in
          </Link>
        </div>
      </form>
    </main>
  );
}
