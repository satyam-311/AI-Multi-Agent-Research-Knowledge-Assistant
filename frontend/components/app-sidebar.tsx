"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Bot,
  ChevronRight,
  FileStack,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquareQuote,
  PanelsTopLeft,
  X
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme-toggle";
import { getAuthSession, logout } from "@/lib/api";

const items = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/upload", label: "Upload Docs", icon: FileStack },
  { href: "/chat", label: "AI Chat", icon: MessageSquareQuote },
  { href: "/documents", label: "Document Manager", icon: PanelsTopLeft }
];

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [userName, setUserName] = useState("Workspace User");

  useEffect(() => {
    const session = getAuthSession();
    if (session?.user.name) {
      setUserName(session.user.name);
    }
  }, []);

  const nav = (
    <aside className="glass shadow-panel h-full rounded-[2rem] border-zinc-800 bg-zinc-950/80 p-4">
      <div className="mb-8 flex items-start justify-between gap-3">
        <Link href="/" className="flex items-center gap-3 rounded-2xl">
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-cyan-500 via-blue-500 to-teal-400 text-white shadow-lg shadow-cyan-500/30">
            <Bot size={19} />
          </span>
          <span>
            <p className="text-sm font-semibold">AI Research</p>
            <p className="text-xs text-muted-foreground">Knowledge Assistant</p>
          </span>
        </Link>
        <div className="hidden md:block">
          <ThemeToggle />
        </div>
      </div>

      <nav className="space-y-2">
        {items.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={cn(
                "group flex items-center gap-3 rounded-2xl border border-transparent px-3 py-3 text-sm transition-all duration-200",
                active
                  ? "border-cyan-500/30 bg-cyan-500/15 text-cyan-50 shadow-lg shadow-cyan-950/30"
                  : "text-zinc-400 hover:border-zinc-800 hover:bg-zinc-900 hover:text-zinc-50"
              )}
            >
              <item.icon size={16} />
              <span className="flex-1">{item.label}</span>
              <ChevronRight
                size={14}
                className={cn(
                  "transition-transform duration-200",
                  active
                    ? "translate-x-0 text-cyan-300"
                    : "translate-x-[-4px] opacity-0 group-hover:translate-x-0 group-hover:opacity-100"
                )}
              />
            </Link>
          );
        })}
      </nav>

      <div className="mt-8 rounded-[1.75rem] border border-zinc-800 bg-gradient-to-br from-zinc-950 via-zinc-900 to-cyan-950 p-4 text-white">
        <p className="text-xs uppercase tracking-[0.16em] text-white/60">Account</p>
        <p className="mt-2 text-lg font-semibold">{userName}</p>
        <p className="mt-1 text-sm text-white/75">
          Your documents and chat history stay grouped under this local account.
        </p>
        <button
          type="button"
          onClick={() => void logout().finally(() => router.replace("/login"))}
          className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/10 px-4 py-2.5 text-sm text-white transition hover:bg-white/15"
        >
          <LogOut size={14} />
          Sign Out
        </button>
      </div>

      <div className="mt-4 flex items-center justify-between rounded-2xl border border-zinc-800 bg-zinc-900/70 px-3 py-3 md:hidden">
        <span className="text-sm text-muted-foreground">Theme</span>
        <ThemeToggle />
      </div>
    </aside>
  );

  return (
    <>
      <div className="flex items-center justify-between md:hidden">
        <Link href="/" className="flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-cyan-500 via-blue-500 to-teal-400 text-white">
            <Bot size={19} />
          </span>
          <div>
            <p className="text-sm font-semibold">AI Research</p>
            <p className="text-xs text-muted-foreground">Knowledge Assistant</p>
          </div>
        </Link>
        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border bg-card/80"
          aria-label="Toggle navigation"
        >
          {open ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>

      <div className="hidden md:sticky md:top-6 md:block">{nav}</div>

      {open && (
        <div className="fixed inset-0 z-50 bg-slate-950/35 backdrop-blur-sm md:hidden">
          <div className="absolute inset-y-4 left-4 w-[min(86vw,360px)]">{nav}</div>
        </div>
      )}
    </>
  );
}
