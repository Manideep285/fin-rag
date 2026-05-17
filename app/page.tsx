"use client";
import { useEffect, useRef, useState } from "react";
import AuthGuard, { useAuth } from "@/components/AuthGuard";
import { api } from "@/lib/api";

type Citation = {
  chunk_id: string;
  source_id: string;
  source_name: string;
  page_num: number | null;
  section: string | null;
  text: string;
  score: number;
};

type Msg = {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  refused?: boolean;
};

function ChatInner() {
  const { principal } = useAuth();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    if (!input.trim() || busy || !principal) return;
    const q = input.trim();
    setInput("");
    setError(null);
    const next: Msg[] = [...messages, { role: "user", content: q }];
    setMessages(next);
    setBusy(true);
    try {
      const res = await api<{
        answer: string;
        citations: Citation[];
        refused: boolean;
        latency_ms: number;
        context_tokens: number;
      }>("/api/query", {
        method: "POST",
        json: {
          project_id: principal.project_id,
          query: q,
          conversation_history: next.slice(-6).map((m) => ({ role: m.role, content: m.content })),
        },
      });
      setMessages([
        ...next,
        {
          role: "assistant",
          content: res.answer,
          citations: res.citations,
          refused: res.refused,
        },
      ]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "request failed";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex-1 flex flex-col items-center bg-zinc-50 dark:bg-black">
      <div className="w-full max-w-3xl flex-1 flex flex-col px-4">
        <div ref={scrollRef} className="flex-1 overflow-y-auto py-6 space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-zinc-500 mt-24">
              <p className="text-lg font-medium">Ask anything about this project&apos;s documents.</p>
              <p className="text-sm mt-1">Answers cite sources. The assistant refuses when context is insufficient.</p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                  m.role === "user"
                    ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                    : m.refused
                    ? "bg-amber-50 text-amber-900 border border-amber-200 dark:bg-amber-900/20 dark:text-amber-100 dark:border-amber-900"
                    : "bg-white border border-zinc-200 dark:bg-zinc-900 dark:border-zinc-800 dark:text-zinc-100"
                }`}
              >
                <div>{m.content}</div>
                {m.citations && m.citations.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-zinc-200 dark:border-zinc-800 space-y-1.5">
                    <div className="text-xs uppercase tracking-wide text-zinc-500">Sources</div>
                    {m.citations.map((c) => (
                      <details key={c.chunk_id} className="text-xs">
                        <summary className="cursor-pointer text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100">
                          {c.source_name}
                          {c.page_num ? ` · p.${c.page_num}` : ""}
                          {c.section ? ` · ${c.section}` : ""}
                          <span className="ml-2 text-zinc-400">score {c.score.toFixed(3)}</span>
                        </summary>
                        <pre className="mt-1 whitespace-pre-wrap text-zinc-500 font-mono text-[11px]">{c.text}</pre>
                      </details>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {busy && (
            <div className="flex justify-start">
              <div className="rounded-2xl px-4 py-2.5 text-sm bg-white border border-zinc-200 dark:bg-zinc-900 dark:border-zinc-800 text-zinc-500">
                Retrieving and composing answer…
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="mb-2 rounded-md bg-red-50 text-red-800 text-sm p-2 border border-red-200 dark:bg-red-950/30 dark:text-red-200 dark:border-red-900">
            {error}
          </div>
        )}

        <form onSubmit={send} className="pb-6 pt-2 flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="Ask a question…"
            rows={2}
            className="flex-1 resize-none rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 dark:focus:ring-zinc-100"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="self-end rounded-xl bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 px-4 py-2 text-sm font-medium disabled:opacity-40"
          >
            Send
          </button>
        </form>
      </div>
    </main>
  );
}

export default function Home() {
  return (
    <AuthGuard>
      <ChatInner />
    </AuthGuard>
  );
}
