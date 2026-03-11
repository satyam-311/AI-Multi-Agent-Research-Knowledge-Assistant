"use client";

import { useEffect, useState } from "react";
import { Activity, ArrowUpRight, Clock3, Database, FileText, Gauge } from "lucide-react";
import { WorkspaceHeader } from "@/components/workspace-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cleanPreview, normalizeHistory, uniqueLatestDocuments } from "@/lib/document-display";
import { getHealth, listChatHistory, listDocuments } from "@/lib/api";

export default function DashboardPage() {
  const [healthStatus, setHealthStatus] = useState("Checking");
  const [documents, setDocuments] = useState<
    Awaited<ReturnType<typeof listDocuments>>
  >([]);
  const [history, setHistory] = useState<Awaited<ReturnType<typeof listChatHistory>>>([]);
  const [stats, setStats] = useState([
    { label: "Documents Indexed", value: "-", icon: FileText },
    { label: "Active Sources", value: "-", icon: Database },
    { label: "Questions Asked", value: "-", icon: Gauge },
    { label: "API Status", value: "Checking", icon: Activity }
  ]);

  useEffect(() => {
    let active = true;

    async function loadDashboard() {
      try {
        const [health, documents, history] = await Promise.all([
          getHealth(),
          listDocuments(),
          listChatHistory()
        ]);
        if (!active) return;

        const latestDocuments = uniqueLatestDocuments(documents);
        const normalizedHistory = normalizeHistory(history);
        setDocuments(latestDocuments);
        setHistory(normalizedHistory);
        setHealthStatus(health.status);
        setStats([
          { label: "Documents", value: String(latestDocuments.length), icon: FileText },
          { label: "Uploads", value: String(documents.length), icon: Database },
          { label: "Questions Asked", value: String(normalizedHistory.length), icon: Gauge },
          { label: "API Status", value: health.status, icon: Activity }
        ]);
      } catch {
        if (!active) return;
        setHealthStatus("Offline");
        setStats([
          { label: "Documents Indexed", value: "-", icon: FileText },
          { label: "Active Sources", value: "-", icon: Database },
          { label: "Questions Asked", value: "-", icon: Gauge },
          { label: "API Status", value: "Offline", icon: Activity }
        ]);
      }
    }

    void loadDashboard();
    return () => {
      active = false;
    };
  }, []);

  return (
    <>
      <WorkspaceHeader
        eyebrow="Workspace"
        title="Dashboard"
        subtitle="Live overview of uploads, recent questions, and the current health of your RAG workspace."
      />
      <Card className="overflow-hidden bg-gradient-to-r from-blue-600 via-sky-500 to-cyan-400 text-white">
        <CardContent className="py-8">
          <p className="text-xs uppercase tracking-[0.16em] text-white/80">Workspace Health</p>
          <h2 className="mt-2 text-2xl font-semibold md:text-3xl">
            {healthStatus === "ok" ? "Workspace Ready" : "Waiting for Connection"}
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-white/90">
            Keep your latest documents, questions, and answers in one place.
          </p>
        </CardContent>
      </Card>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((item) => (
          <Card key={item.label}>
            <CardHeader className="pb-1">
              <CardTitle className="text-sm text-muted-foreground">{item.label}</CardTitle>
            </CardHeader>
            <CardContent className="flex items-center justify-between pt-1">
              <p className="text-2xl font-semibold">{item.value}</p>
              <span className="grid h-10 w-10 place-items-center rounded-2xl bg-slate-100 text-primary">
                <item.icon size={18} />
              </span>
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Uploaded Documents</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                Latest unique documents in your workspace.
              </p>
            </div>
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              View all <ArrowUpRight size={13} />
            </span>
          </CardHeader>
          <CardContent className="space-y-3">
            {documents.length === 0 && (
              <div className="rounded-[1.5rem] border bg-muted/30 p-4 text-sm text-muted-foreground">
                No documents uploaded yet.
              </div>
            )}
            {documents.slice(0, 4).map((document) => (
              <div
                key={document.id}
                className="flex flex-col gap-2 rounded-[1.5rem] border bg-card/70 p-4 md:flex-row md:items-start md:justify-between"
              >
                <div>
                  <p className="font-semibold">{document.filename}</p>
                  <p className="mt-1 text-xs text-muted-foreground">Document #{document.id}</p>
                  <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                    {cleanPreview(document.content_preview)}
                  </p>
                </div>
                <div className="inline-flex items-center gap-1 rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
                  <Clock3 size={12} />
                  {new Date(document.created_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Chat Activity</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              Recent questions and answers from your workspace.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {history.length === 0 && (
              <div className="rounded-[1.5rem] border bg-muted/30 p-4 text-sm text-muted-foreground">
                No chat history yet. Ask a question after uploading a document.
              </div>
            )}
            {history.slice(0, 4).map((item) => (
              <div key={item.id} className="rounded-[1.5rem] border bg-card/70 p-4">
                <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  Question
                </p>
                <p className="mt-1 font-medium">{item.question}</p>
                <p className="mt-3 line-clamp-3 text-sm text-muted-foreground">{item.answer}</p>
                {item.sources.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.sources.slice(0, 3).map((source) => (
                      <span
                        key={`${item.id}-${source}`}
                        className="rounded-full border bg-muted px-2.5 py-1 text-xs text-muted-foreground"
                      >
                        {source}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
