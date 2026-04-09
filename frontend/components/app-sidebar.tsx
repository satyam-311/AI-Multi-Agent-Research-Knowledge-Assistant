"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import {
  Bot,
  FileStack,
  LogOut,
  Menu,
  MessageSquareQuote,
  PanelsTopLeft,
  X
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/components/auth-provider";

const items = [
  { href: "/dashboard", label: "Chat", icon: MessageSquareQuote },
  { href: "/upload", label: "Upload", icon: FileStack },
  { href: "/documents", label: "Documents", icon: PanelsTopLeft }
];

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const { user, logout } = useAuth();
  const userName = user?.name ?? "Workspace User";
  const userEmail = user?.email ?? "google account";
  const nav = (
    <aside className="h-full rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-900 dark:bg-zinc-950">
      <div className="mb-6 flex items-start justify-between gap-3">
        <Link href="/" className="flex items-center gap-3 rounded-2xl">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-zinc-950 text-white dark:bg-white dark:text-zinc-950">
            <Bot size={18} />
          </span>
          <span>
            <p className="text-sm font-semibold">Research AI</p>
            <p className="text-xs text-muted-foreground">Chat-first workspace</p>
          </span>
        </Link>
      </div>

      <nav className="space-y-1">
        {items.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition",
                active
                  ? "bg-zinc-950 text-white dark:bg-white dark:text-zinc-950"
                  : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-white"
              )}
            >
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-black/5 dark:bg-white/5">
                <item.icon size={15} />
              </span>
              <span className="flex-1">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-6 rounded-2xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <p className="text-sm font-semibold text-zinc-950 dark:text-white">{userName}</p>
        <p className="mt-1 text-xs text-zinc-500">{userEmail}</p>
        <button
          type="button"
          onClick={() => void logout().finally(() => router.replace("/login"))}
          className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-700 transition hover:border-zinc-300 hover:text-zinc-950 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-300 dark:hover:border-zinc-700 dark:hover:text-white"
        >
          <LogOut size={14} />
          Sign Out
        </button>
      </div>
    </aside>
  );

  return (
    <>
      <div className="flex items-center justify-between md:hidden">
        <Link href="/" className="flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-zinc-950 text-white dark:bg-white dark:text-zinc-950">
            <Bot size={19} />
          </span>
          <div>
            <p className="text-sm font-semibold">Research AI</p>
            <p className="text-xs text-muted-foreground">Chat-first workspace</p>
          </div>
        </Link>
        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950"
          aria-label="Toggle navigation"
        >
          {open ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>

      <div className="hidden md:sticky md:top-6 md:block">{nav}</div>

      {open && (
        <div className="fixed inset-0 z-50 bg-black/30 md:hidden">
          <div className="absolute inset-y-4 left-4 w-[min(86vw,360px)]">{nav}</div>
        </div>
      )}
    </>
  );
}
