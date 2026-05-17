"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { logout } from "@/lib/api";
import { useAuth } from "./AuthGuard";

export default function TopNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { principal } = useAuth();

  const link = (href: string, label: string) => {
    const active = pathname === href || (href !== "/" && pathname?.startsWith(href));
    return (
      <Link
        key={href}
        href={href}
        className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
          active
            ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
            : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
        }`}
      >
        {label}
      </Link>
    );
  };

  return (
    <header className="sticky top-0 z-10 border-b border-zinc-200 dark:border-zinc-800 bg-white/80 dark:bg-black/80 backdrop-blur">
      <div className="mx-auto max-w-6xl flex items-center justify-between px-4 h-12">
        <div className="flex items-center gap-1">
          <Link href="/" className="font-semibold tracking-tight mr-3">fin-rag</Link>
          {link("/", "Chat")}
          {principal && link("/history", "History")}
          {principal?.role === "admin" && link("/admin", "Admin")}
        </div>
        <div className="flex items-center gap-3 text-xs text-zinc-500">
          {principal && (
            <span>
              project <code className="font-mono">{principal.project_id.slice(0, 8)}</code> · {principal.role}
            </span>
          )}
          {principal && (
            <button
              type="button"
              className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
              onClick={() => {
                logout();
                router.replace("/login");
              }}
            >
              Sign out
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
