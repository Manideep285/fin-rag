"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import AuthGuard from "@/components/AuthGuard";

const TABS = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/projects", label: "Projects" },
  { href: "/admin/users", label: "Users & roles" },
  { href: "/admin/invite-keys", label: "Invite keys" },
  { href: "/admin/sources", label: "Sources" },
  { href: "/admin/rules", label: "Auto-approval rules" },
  { href: "/admin/index-versions", label: "Index versions" },
  { href: "/admin/observability", label: "Observability" },
  { href: "/admin/eval", label: "Evaluation" },
  { href: "/admin/refusals", label: "Refusals" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <AuthGuard requireAdmin>
      <div className="flex-1 flex">
        <aside className="w-56 shrink-0 border-r border-zinc-200 dark:border-zinc-800 bg-white dark:bg-black">
          <nav className="p-3 space-y-0.5">
            {TABS.map((t) => {
              const active = pathname === t.href;
              return (
                <Link
                  key={t.href}
                  href={t.href}
                  className={`block px-3 py-1.5 rounded-md text-sm ${
                    active
                      ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                      : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
                  }`}
                >
                  {t.label}
                </Link>
              );
            })}
          </nav>
        </aside>
        <section className="flex-1 overflow-auto">
          <div className="mx-auto max-w-5xl p-6">{children}</div>
        </section>
      </div>
    </AuthGuard>
  );
}
