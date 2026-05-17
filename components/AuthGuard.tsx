"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { decodeJwt, getToken, setToken } from "@/lib/api";

export type Principal = {
  user_id: string;
  project_id: string;
  role: string;
};

export function useAuth(): { ready: boolean; principal: Principal | null } {
  const [ready, setReady] = useState(false);
  const [principal, setPrincipal] = useState<Principal | null>(null);
  useEffect(() => {
    const t = getToken();
    if (!t) {
      setReady(true);
      return;
    }
    const payload = decodeJwt(t);
    if (!payload) {
      setReady(true);
      return;
    }
    // Check JWT expiration — auto-clear expired tokens
    const exp = payload.exp as number | undefined;
    if (exp && exp * 1000 < Date.now()) {
      setToken(null);
      setReady(true);
      return;
    }
    setPrincipal({
      user_id: String(payload.sub),
      project_id: String(payload.pid),
      role: String(payload.role || "viewer"),
    });
    setReady(true);
  }, []);
  return { ready, principal };
}

export default function AuthGuard({
  children,
  requireAdmin = false,
}: {
  children: React.ReactNode;
  requireAdmin?: boolean;
}) {
  const router = useRouter();
  const { ready, principal } = useAuth();

  useEffect(() => {
    if (!ready) return;
    if (!principal) {
      router.replace("/login");
      return;
    }
    if (requireAdmin && principal.role !== "admin") {
      router.replace("/");
    }
  }, [ready, principal, requireAdmin, router]);

  if (!ready) {
    return <div className="p-8 text-zinc-500">Loading…</div>;
  }
  if (!principal) return null;
  if (requireAdmin && principal.role !== "admin") return null;
  return <>{children}</>;
}
