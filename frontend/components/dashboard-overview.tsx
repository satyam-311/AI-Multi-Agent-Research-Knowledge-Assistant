"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  ArrowRight,
  BookOpenText,
  BrainCircuit,
  Clock3,
  Database,
  FileText,
  Gauge,
  MessageSquareText,
  Plus,
  Sparkles,
  TrendingUp
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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

export type DashboardOverviewProps = {
  healthStatus: string;
  documents: DocumentRecord[];
  history: ChatHistoryRecord[];
  apiLatencyMs: number | null;
  lastUpdatedLabel: string;
  stats: StatCard[];
};

const quickActions: QuickAction[] = [
  {
    label: "Upload PDF",
    href: "/upload",
    icon: Plus,
    detail: "Add a new research source"
  },
  {
    label: "Open Chat",
    href: "/chat",
    icon: MessageSquareText,
    detail: "Ask grounded questions"
  },
  {
    label: "Manage Docs",
    href: "/documents",
    icon: BookOpenText,
    detail: "Review indexed files"
  }
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

export function DashboardOverview({
  healthStatus,
  documents,
  history,
  apiLatencyMs,
  lastUpdatedLabel,
  stats
}: DashboardOverviewProps) {
  const router = useRouter();
  const latestDocument = documents[0];
  const latestQuestion = history[0];
  const healthy = healthStatus === "ok";
  const totalSources = history.reduce((sum, item) => sum + item.sources.length, 0);
  const avgSources = history.length ? (totalSources / history.length).toFixed(1) : "0.0";
  const queryPlaceholder =
    latestQuestion?.question ?? "Ask the assistant to synthesize findings across your papers";

  const submitPrompt = (prompt: string) => {
    router.push(`/chat?prompt=${encodeURIComponent(prompt)}`);
  };

  return (
    <div className="space-y-4">
      <Card className="border-zinc-800 bg-zinc-950/80">
        <CardContent className="flex flex-col gap-4 py-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-cyan-300/75">Quick Actions</p>
            <h2 className="mt-2 text-xl font-semibold text-white">Run your research workflow faster</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Move from upload to analysis without hunting through the workspace.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {quickActions.map((action) => (
              <Link
                key={action.href}
                href={action.href}
                className="group rounded-[1.5rem] border border-zinc-800 bg-zinc-900/70 px-4 py-3 transition hover:border-cyan-500/35 hover:bg-zinc-900"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="grid h-10 w-10 place-items-center rounded-2xl bg-cyan-500/12 text-cyan-200">
                    <action.icon size={16} />
                  </span>
                  <ArrowRight
                    size={15}
                    className="text-zinc-500 transition group-hover:translate-x-1 group-hover:text-cyan-200"
                  />
                </div>
                <p className="mt-3 text-sm font-semibold text-white">{action.label}</p>
                <p className="mt-1 text-xs text-muted-foreground">{action.detail}</p>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <HealthStatusCard
          healthStatus={healthStatus}
          apiLatencyMs={apiLatencyMs}
          documentsCount={documents.length}
          questionCount={history.length}
          lastUpdatedLabel={lastUpdatedLabel}
          avgSources={avgSources}
        />
        <AIQuickQueryCard
          placeholder={queryPlaceholder}
          onSubmit={submitPrompt}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <StatInsightCard key={stat.label} {...stat} />
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <DocumentsPanel latestDocument={latestDocument} documents={documents} />
        <ActivityPanel latestQuestion={latestQuestion} history={history} healthy={healthy} />
      </div>
    </div>
  );
}

function HealthStatusCard({
  healthStatus,
  apiLatencyMs,
  documentsCount,
  questionCount,
  lastUpdatedLabel,
  avgSources
}: {
  healthStatus: string;
  apiLatencyMs: number | null;
  documentsCount: number;
  questionCount: number;
  lastUpdatedLabel: string;
  avgSources: string;
}) {
  const healthy = healthStatus === "ok";

  return (
    <Card className="overflow-hidden border-emerald-500/10 bg-[radial-gradient(circle_at_top_left,_rgba(34,197,94,0.22),_transparent_30%),linear-gradient(180deg,rgba(9,14,20,0.98),rgba(9,12,18,0.94))]">
      <CardContent className="space-y-6 py-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-emerald-300/80">API Control Center</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">
              {healthy ? "Backend healthy and responsive" : "Connection needs attention"}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-300">
              Monitor retrieval availability, response speed, and document readiness in one place.
            </p>
          </div>
          <span
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium ${
              healthy
                ? "border-emerald-500/30 bg-emerald-500/12 text-emerald-100"
                : "border-amber-500/30 bg-amber-500/12 text-amber-100"
            }`}
          >
            <span
              className={`h-2.5 w-2.5 rounded-full ${healthy ? "bg-emerald-400" : "bg-amber-300"}`}
            />
            {healthy ? "Operational" : "Checking"}
          </span>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricPill
            label="Status"
            value={healthy ? "Online" : healthStatus}
            icon={Activity}
          />
          <MetricPill
            label="Latency"
            value={apiLatencyMs === null ? "..." : `${apiLatencyMs} ms`}
            icon={Gauge}
          />
          <MetricPill
            label="Indexed docs"
            value={String(documentsCount)}
            icon={FileText}
          />
          <MetricPill
            label="Avg sources"
            value={avgSources}
            icon={Database}
          />
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <InsightStrip
            title="Last sync"
            value={lastUpdatedLabel}
            detail="Dashboard snapshot refreshed"
          />
          <InsightStrip
            title="Question volume"
            value={`${questionCount} total`}
            detail="Saved research interactions"
          />
          <InsightStrip
            title="Readiness"
            value={healthy ? "Ready to answer" : "Awaiting backend"}
            detail="Query pipeline availability"
          />
        </div>
      </CardContent>
    </Card>
  );
}

function AIQuickQueryCard({
  placeholder,
  onSubmit
}: {
  placeholder: string;
  onSubmit: (prompt: string) => void;
}) {
  return (
    <Card className="border-cyan-500/10 bg-[radial-gradient(circle_at_top_right,_rgba(34,211,238,0.2),_transparent_30%),linear-gradient(180deg,rgba(10,12,18,0.98),rgba(9,11,17,0.94))]">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-cyan-300/80">AI Workspace</p>
            <CardTitle className="mt-2 text-white">Quick Query</CardTitle>
          </div>
          <span className="inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-cyan-100">
            <Sparkles size={12} />
            assistant
          </span>
        </div>
        <p className="text-sm leading-6 text-zinc-300">
          Jump directly into analysis with a prefilled research question.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <button
          type="button"
          onClick={() => onSubmit(placeholder)}
          className="w-full rounded-[1.5rem] border border-zinc-800 bg-zinc-900/80 px-4 py-4 text-left transition hover:border-cyan-500/35"
        >
          <p className="text-xs uppercase tracking-[0.16em] text-zinc-500">Suggested starting point</p>
          <p className="mt-2 text-sm leading-6 text-white">{placeholder}</p>
        </button>

        <div className="grid gap-2">
          {suggestionPrompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => onSubmit(prompt)}
              className="rounded-2xl border border-zinc-800 bg-zinc-900/55 px-4 py-3 text-left text-sm text-zinc-200 transition hover:border-cyan-500/30 hover:text-white"
            >
              {prompt}
            </button>
          ))}
        </div>

        <div className="flex gap-2 rounded-[1.5rem] border border-zinc-800 bg-zinc-950/80 p-2">
          <Input
            readOnly
            value="Open AI Chat to write a custom prompt"
            className="border-0 bg-transparent text-zinc-400"
          />
          <Button className="gap-2 rounded-2xl" onClick={() => onSubmit(placeholder)}>
            <BrainCircuit size={15} />
            Ask AI
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function StatInsightCard({ label, value, change, icon: Icon, note, accent }: StatCard) {
  return (
    <Card className={`overflow-hidden border-white/5 bg-gradient-to-br ${accent}`}>
      <CardContent className="py-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.16em] text-white/45">{label}</p>
            <p className="mt-3 text-3xl font-semibold leading-none text-white">{value}</p>
          </div>
          <span className="grid h-11 w-11 place-items-center rounded-2xl border border-white/10 bg-white/10 text-white">
            <Icon size={18} />
          </span>
        </div>
        <div className="mt-5 flex items-center justify-between gap-3">
          <p className="max-w-[12rem] text-sm leading-5 text-white/65">{note}</p>
          <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs font-medium text-white/85">
            <TrendingUp size={12} />
            {change}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function DocumentsPanel({
  latestDocument,
  documents
}: {
  latestDocument: DocumentRecord | undefined;
  documents: DocumentRecord[];
}) {
  return (
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
  );
}

function ActivityPanel({
  latestQuestion,
  history,
  healthy
}: {
  latestQuestion: ChatHistoryRecord | undefined;
  history: ChatHistoryRecord[];
  healthy: boolean;
}) {
  return (
    <Card className="border-zinc-800 bg-zinc-950/80">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="text-white">Recent Chat Activity</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Preserve context, track the latest questions, and see what the assistant referenced.
          </p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            healthy ? "bg-emerald-500/12 text-emerald-100" : "bg-amber-500/12 text-amber-100"
          }`}
        >
          {healthy ? "Live answers" : "Paused"}
        </span>
      </CardHeader>
      <CardContent className="space-y-3">
        {history.length === 0 && (
          <div className="rounded-[1.5rem] border border-zinc-800 bg-zinc-900/55 p-4 text-sm text-muted-foreground">
            No chat history yet. Start with one of the suggested prompts.
          </div>
        )}
        {latestQuestion && (
          <div className="rounded-[1.75rem] border border-zinc-800 bg-zinc-900/70 p-5">
            <p className="text-xs uppercase tracking-[0.16em] text-zinc-500">Most recent question</p>
            <p className="mt-2 text-lg font-semibold text-white">{latestQuestion.question}</p>
            <p className="mt-3 line-clamp-4 text-sm leading-6 text-zinc-300">
              {latestQuestion.answer}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {latestQuestion.sources.slice(0, 4).map((source) => (
                <span
                  key={`${latestQuestion.id}-${source}`}
                  className="rounded-full border border-zinc-700 bg-zinc-950 px-2.5 py-1 text-xs text-zinc-300"
                >
                  {source}
                </span>
              ))}
            </div>
          </div>
        )}
        {history.slice(1, 4).map((item) => (
          <div key={item.id} className="rounded-[1.5rem] border border-zinc-800 bg-zinc-900/55 p-4">
            <div className="flex items-start justify-between gap-3">
              <p className="line-clamp-2 text-sm font-semibold text-white">{item.question}</p>
              <span className="shrink-0 text-xs text-zinc-500">{relativeAge(item.created_at)}</span>
            </div>
            <p className="mt-2 line-clamp-3 text-sm leading-6 text-muted-foreground">
              {item.answer}
            </p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function MetricPill({
  label,
  value,
  icon: Icon
}: {
  label: string;
  value: string;
  icon: typeof Activity;
}) {
  return (
    <div className="rounded-[1.5rem] border border-white/8 bg-white/[0.04] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs uppercase tracking-[0.16em] text-zinc-500">{label}</p>
        <Icon size={15} className="text-zinc-400" />
      </div>
      <p className="mt-3 text-xl font-semibold text-white">{value}</p>
    </div>
  );
}

function InsightStrip({
  title,
  value,
  detail
}: {
  title: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-[1.5rem] border border-zinc-800 bg-zinc-950/70 p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-zinc-500">{title}</p>
      <p className="mt-2 text-sm font-semibold text-white">{value}</p>
      <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
    </div>
  );
}
