// Thin browser-side API client. Uses localStorage for the bearer token.
// Pilot-grade — production should switch to httpOnly cookies set by a
// Next.js route handler that proxies /auth/* to the FastAPI backend.

export const API_BASE: string =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const TOKEN_KEY = "finrag.token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t === null) window.localStorage.removeItem(TOKEN_KEY);
  else window.localStorage.setItem(TOKEN_KEY, t);
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

export async function api<T = unknown>(
  path: string,
  init: RequestInit & { json?: unknown; auth?: boolean } = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  const auth = init.auth !== false;
  if (auth) {
    const tok = getToken();
    if (tok) headers.set("Authorization", `Bearer ${tok}`);
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    body: init.json !== undefined ? JSON.stringify(init.json) : init.body,
    cache: "no-store",
  });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      try { body = await res.text(); } catch { /* ignore */ }
    }
    const msg =
      typeof body === "object" && body && "detail" in (body as Record<string, unknown>)
        ? String((body as { detail: unknown }).detail)
        : `HTTP ${res.status}`;
    throw new ApiError(res.status, msg, body);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}

// ---- helpers --------------------------------------------------------------

export type Token = { access_token: string; expires_in: number };

export async function login(email: string, password: string): Promise<Token> {
  const t = await api<Token>("/auth/login", {
    method: "POST",
    json: { email, password },
    auth: false,
  });
  setToken(t.access_token);
  return t;
}

export async function signup(input: {
  email: string;
  password: string;
  display_name?: string;
  invite_key: string;
}): Promise<Token> {
  const t = await api<Token>("/auth/signup", {
    method: "POST",
    json: input,
    auth: false,
  });
  setToken(t.access_token);
  return t;
}

export function logout() {
  setToken(null);
}

export function decodeJwt(token: string): Record<string, unknown> | null {
  try {
    const part = token.split(".")[1];
    const json = atob(part.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}
