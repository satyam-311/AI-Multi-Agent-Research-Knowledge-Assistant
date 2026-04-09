"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BookOpenText,
  Clock3,
  FileText,
  MessageSquare,
  MessageSquareText,
  Plus,
  Search,
  Sparkles,
  TrendingUp
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cleanPreview } from "@/lib/document-display";
import type { ChatHistoryRecord, DocumentRecord } from "@/lib/api";

type StatCard = {
  label: string;
  value: string;
  change: string;
  icon: typeof FileText;
  note: string;
  accent: string;
};

type QuickAction = {
  label: string;
  href: string;
  icon: typeof Plus;
  detail: string;
};

export type DashboardOverviewV2Props = {
  healthStatus: string;
  documents: DocumentRecord[];
  history: ChatHistoryRecord[];
  apiLatencyMs: number | null;
  lastUpdatedLabel: string;
  stats: StatCard[];
};

const quickActions: QuickAction[] = [
  { label: "Upload PDF", href: "/upload", icon: Plus, detail: "Add a new research source" },
  { label: "Open Chat", href: "/chat", icon: MessageSquareText, detail: "Ask grounded questions" },
  { label: "Manage Docs", href: "/documents", icon: BookOpenText, detail: "Review indexed files" }
];

const suggestionPrompts = [
  "Summarize the most important findings across my uploaded papers",
  "List evaluation metrics mentioned in the latest document",
  "Compare the main methods discussed in my workspace"
];

function formatDateTime(value: string) {
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
}

function relativeAge(value: string) {
  const diff = Date.now() - new Date(value).getTime();
  const minutes = Math.max(1, Math.round(diff / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function DashboardOverviewV2({
  healthStatus,
  documents,
  history,
  apiLatencyMs,
  lastUpdatedLabel,
  stats
}: DashboardOverviewV2Props) {
  const router = useRouter();
  const latestDocument = documents[0];
  const healthy = healthStatus === "ok";
  const queryPlaceholder =
    history[0]?.question ?? "Ask the assistant to synthesize findings across your papers";

  const submitPrompt = (prompt: string) => {
    router.push(`/chat?prompt=${encodeURIComponent(prompt)}`);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Last updated {lastUpdatedLabel}
          {apiLatencyMs !== null ? ` • ${apiLatencyMs} ms` : ""}
        </p>
        <span
          className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${
            healthy
              ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-100"
              : "border-amber-500/25 bg-amber-500/10 text-amber-100"
          }`}
        >
          <span
            className={`h-2 w-2 rounded-full ${healthy ? "bg-emerald-400" : "bg-amber-300"}`}
          />
          {healthy ? "System OK" : "System checking"}
        </span>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
        <Card className="border-cyan-500/10 bg-[radial-gradient(circle_at_top_right,_rgba(34,211,238,0.2),_transparent_30%),linear-gradient(180deg,rgba(10,12,18,0.98),rgba(9,11,17,0.94))]">
          <CardContent className="space-y-5 py-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-cyan-300/80">Ask AI</p>
                <h2 className="mt-2 text-2xl font-semibold text-white">Ask AI about your documents</h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-300">
                  Query your uploaded research, compare methods, summarize findings, or extract evidence in one step.
                </p>
              </div>
              <span className="inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-cyan-100">
                <Sparkles size={12} />
                research assistant
              </span>
            </div>

            <button
              type="button"
              onClick={() => submitPrompt(queryPlaceholder)}
              className="w-full rounded-[1.75rem] border border-zinc-800 bg-zinc-900/80 px-5 py-5 text-left transition hover:border-cyan-500/35 hover:bg-zinc-900"
            >
              <div className="flex items-center gap-3">
                <span className="grid h-11 w-11 place-items-center rounded-2xl bg-cyan-500/12 text-cyan-200">
                  <Search size={18} />
                </span>
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-zinc-500">Ask AI about your documents</p>
                  <p className="mt-1 text-base text-white">{queryPlaceholder}</p>
                </div>
              </div>
            </button>

            <div className="grid gap-2 md:grid-cols-3">
              {suggestionPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => submitPrompt(prompt)}
                  className="rounded-[1.25rem] border border-zinc-800 bg-zinc-900/55 px-4 py-3 text-left text-sm text-zinc-200 transition hover:border-cyan-500/30 hover:text-white"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="border-zinc-800 bg-zinc-950/80">
          <CardContent className="flex h-full flex-col gap-4 py-5">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-cyan-300/75">Quick Actions</p>
              <h2 className="mt-2 text-xl font-semibold text-white">Run your research workflow faster</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Prioritize uploads, questions, and document management.
              </p>
            </div>
            <div className="grid gap-3">
              {quickActions.map((action) => (
                <Link
                  key={action.href}
                  href={action.href}
                  className="group rounded-[1.5rem] border border-zinc-800 bg-zinc-900/70 px-4 py-3 transition hover:border-cyan-500/35 hover:bg-zinc-900"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span className="grid h-10 w-10 place-items-center rounded-2xl bg-cyan-500/12 text-cyan-200">
                        <action.icon size={16} />
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-white">{action.label}</p>
                        <p className="text-xs text-muted-foreground">{action.detail}</p>
                      </div>
                    </div>
                    <ArrowRight
                      size={15}
                      className="text-zinc-500 transition group-hover:translate-x-1 group-hover:text-cyan-200"
                    />
                  </div>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label} className={`overflow-hidden border-white/5 bg-gradient-to-br ${stat.accent}`}>
            <CardContent className="py-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-white/45">{stat.label}</p>
                  <p className="mt-3 text-3xl font-semibold leading-none text-white">{stat.value}</p>
                </div>
                <span className="grid h-11 w-11 place-items-center rounded-2xl border border-white/10 bg-white/10 text-white">
                  <stat.icon size={18} />
                </span>
              </div>
              <div className="mt-5 flex items-center justify-between gap-3">
                <p className="max-w-[12rem] text-sm leading-5 text-white/65">{stat.note}</p>
                <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs font-medium text-white/85">
                  <TrendingUp size={12} />
                  {stat.change}
                </span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <Card className="border-zinc-800 bg-zinc-950/80">
          <CardHeader className="flex flex-row items-start justify-between gap-4">
            <div>
              <CardTitle className="text-white">Recent Queries</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                Return to previous research threads or reopen a prompt in one click.
              </p>
            </div>
            <span className="rounded-full bg-zinc-900 px-3 py-1 text-xs font-medium text-zinc-400">
              {history.length} saved
            </span>
          </CardHeader>
          <CardContent className="space-y-3">
            {history.length === 0 && (
              <div className="rounded-[1.5rem] border border-zinc-800 bg-zinc-900/55 p-4 text-sm text-muted-foreground">
                No chat history yet. Start with one of the suggested prompts.
              </div>
            )}
            {history.slice(0, 5).map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => submitPrompt(item.question)}
                className="w-full rounded-[1.5rem] border border-zinc-800 bg-zinc-900/55 p-4 text-left transition hover:border-cyan-500/25 hover:bg-zinc-900"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-cyan-500/10 text-cyan-200">
                      <MessageSquare size={15} />
                    </span>
                    <div className="min-w-0">
                      <p className="line-clamp-2 text-sm font-semibold text-white">{item.question}</p>
                      <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted-foreground">
                        {item.answer}
                      </p>
                    </div>
                  </div>
                  <span className="shrink-0 text-xs text-zinc-500">{relativeAge(item.created_at)}</span>
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card className="border-zinc-800 bg-zinc-950/80">
          <CardHeader className="flex flex-row items-start justify-between gap-4">
            <div>
              <CardTitle className="text-white">Uploaded Documents</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                Clear metadata, cleaner previews, and faster access to the latest sources.
              </p>
            </div>
            <Link
              href="/documents"
              className="inline-flex items-center gap-1 text-xs text-cyan-200 transition hover:text-cyan-100"
            >
              View library
              <ArrowRight size={13} />
            </Link>
          </CardHeader>
          <CardContent className="space-y-3">
            {documents.length === 0 && (
              <div className="rounded-[1.5rem] border border-zinc-800 bg-zinc-900/55 p-4 text-sm text-muted-foreground">
                No documents uploaded yet.
              </div>
            )}
            {latestDocument && (
              <div className="rounded-[1.75rem] border border-cyan-500/20 bg-cyan-500/8 p-5">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-cyan-200/75">Latest indexed</p>
                    <p className="mt-2 text-lg font-semibold text-white">{latestDocument.filename}</p>
                    <p className="mt-2 text-sm leading-6 text-zinc-300">
                      {cleanPreview(latestDocument.content_preview, 220)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-cyan-500/15 bg-zinc-950/60 px-3 py-2 text-right">
                    <p className="text-xs uppercase tracking-[0.16em] text-zinc-500">Added</p>
                    <p className="mt-1 text-sm font-medium text-white">
                      {formatDateTime(latestDocument.created_at)}
                    </p>
                  </div>
                </div>
              </div>
            )}
            {documents.slice(1, 4).map((document) => (
              <div
                key={document.id}
                className="flex flex-col gap-3 rounded-[1.5rem] border border-zinc-800 bg-zinc-900/60 p-4 md:flex-row md:items-start md:justify-between"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">{document.filename}</p>
                  <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted-foreground">
                    {cleanPreview(document.content_preview, 160)}
                  </p>
                </div>
                <div className="shrink-0">
                  <span className="inline-flex items-center gap-1 rounded-full border border-zinc-700 bg-zinc-950 px-3 py-1 text-xs text-zinc-400">
                    <Clock3 size={12} />
                    {relativeAge(document.created_at)}
                  </span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="fixed bottom-6 right-6 z-40">
        <button
          type="button"
          onClick={() => submitPrompt(queryPlaceholder)}
          className="inline-flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-cyan-900/35 transition hover:scale-[1.02] hover:bg-cyan-400"
        >
          <Sparkles size={16} />
          Ask AI
        </button>
      </div>
    </div>
  );
}
