"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Bot,
  ArrowUpRight,
  Copy,
  FileStack,
  LoaderCircle,
  RefreshCcw,
  SendHorizontal,
  User2
} from "lucide-react";
import { MarkdownMessage } from "@/components/markdown-message";
import { useToast } from "@/components/toast-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cleanPreview, dedupeSources, normalizeHistory, uniqueLatestDocuments } from "@/lib/document-display";
import { askQuestion, listChatHistory, listDocuments, type DocumentRecord } from "@/lib/api";

type ChatMessage = {
  id: string;
  role: "user" | "ai";
  content: string;
  sources?: string[];
};

const initialMessages: ChatMessage[] = [
  {
    id: "1",
    role: "ai",
    content: "Upload one or more PDFs, then ask a question. I will answer using your documents."
  }
];

type SourceEntry = { label: string; href: string | null };

function parseSourceEntry(source: string): SourceEntry {
  const separator = " | ";
  const separatorIndex = source.lastIndexOf(separator);
  if (separatorIndex === -1) {
    return { label: source, href: null };
  }

  const label = source.slice(0, separatorIndex).trim();
  const href = source.slice(separatorIndex + separator.length).trim();
  if (!href.startsWith("http://") && !href.startsWith("https://")) {
    return { label: source, href: null };
  }
  return { label: label || href, href };
}

function groupSources(sources: string[]) {
  const grouped = {
    pdf: [] as SourceEntry[],
    arxiv: [] as SourceEntry[],
    resources: [] as SourceEntry[]
  };

  for (const source of dedupeSources(sources)) {
    const entry = parseSourceEntry(source);
    const labelLower = entry.label.toLowerCase();
    const hrefLower = entry.href?.toLowerCase() ?? "";

    if (labelLower.endsWith(".pdf")) {
      grouped.pdf.push(entry);
    } else if (
      hrefLower.includes("youtube.com") ||
      hrefLower.includes("duckduckgo.com") ||
      hrefLower.includes("scholar.google.com") ||
      hrefLower.includes("github.com")
    ) {
      grouped.resources.push(entry);
    } else {
      grouped.arxiv.push(entry);
    }
  }

  return grouped;
}

function SourceBlock({ title, items }: { title: string; items: SourceEntry[] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-zinc-500">{title}</p>
      <div className="flex flex-wrap gap-2">
        {items.map((item, index) =>
          item.href ? (
            <a
              key={`${title}-${item.label}-${index}`}
              href={item.href}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:border-zinc-300 hover:text-zinc-950 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-200 dark:hover:border-zinc-700 dark:hover:text-white"
            >
              {item.label}
              <ArrowUpRight size={12} />
            </a>
          ) : (
            <span
              key={`${title}-${item.label}-${index}`}
              className="inline-flex items-center rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-300"
            >
              {item.label}
            </span>
          )
        )}
      </div>
    </div>
  );
}

export function ChatWorkspace({ showSidebar = true }: { showSidebar?: boolean }) {
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | "all">("all");
  const [error, setError] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState("");
  const viewportRef = useRef<HTMLDivElement>(null);
  const latestDocuments = useMemo(() => documents.slice(0, 5), [documents]);

  useEffect(() => {
    const prompt = searchParams?.get("prompt");
    if (!prompt) {
      return;
    }

    setInput(prompt);
  }, [searchParams]);

  useEffect(() => {
    viewportRef.current?.scrollTo({
      top: viewportRef.current.scrollHeight,
      behavior: "smooth"
    });
  }, [messages, loading]);

  useEffect(() => {
    if (!error) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setError(null);
    }, 5000);

    return () => window.clearTimeout(timeout);
  }, [error]);

  useEffect(() => {
    let active = true;

    async function loadWorkspace() {
      try {
        const [documentRows, historyRows] = await Promise.all([listDocuments(), listChatHistory()]);
        if (!active) return;

        setDocuments(uniqueLatestDocuments(documentRows));
        if (historyRows.length > 0) {
          const restoredMessages: ChatMessage[] = normalizeHistory(historyRows)
            .slice()
            .reverse()
            .flatMap((item) => [
              {
                id: `q-${item.id}`,
                role: "user" as const,
                content: item.question
              },
              {
                id: `a-${item.id}`,
                role: "ai" as const,
                content: item.answer,
                sources: item.sources
              }
            ]);
        setMessages(restoredMessages);
        }
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load chat data.");
        toast({
          variant: "error",
          title: "History unavailable",
          description:
            loadError instanceof Error ? loadError.message : "Could not load chat data."
        });
      } finally {
        if (active) {
          setHistoryLoading(false);
        }
      }
    }

    void loadWorkspace();
    return () => {
      active = false;
    };
  }, []);

  const handleSubmitQuestion = async () => {
    const question = input.trim();
    if (!question || loading) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: question
    };

    setLastQuestion(question);
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const response = await askQuestion({
        question,
        documentId: selectedDocumentId === "all" ? null : selectedDocumentId
      });
      const aiMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "ai",
        content: response.answer,
        sources: dedupeSources(response.sources)
      };
      setMessages((prev) => [...prev, aiMessage]);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Question failed.");
      toast({
        variant: "error",
        title: "Question failed",
        description:
          submitError instanceof Error ? submitError.message : "The assistant could not respond."
      });
    } finally {
      setLoading(false);
    }
  };

  const retryLastQuestion = () => {
    if (!lastQuestion || loading) {
      return;
    }
    setInput(lastQuestion);
  };

  const copyMessage = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      toast({
        variant: "success",
        title: "Copied response",
        description: "Assistant message copied to clipboard."
      });
    } catch {
      toast({
        variant: "error",
        title: "Copy failed",
        description: "Clipboard access was not available."
      });
    }
  };

  const handleComposerKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSubmitQuestion();
    }
  };

  return (
    <div className={`grid gap-5 ${showSidebar ? "xl:grid-cols-[minmax(0,1fr)_250px]" : ""}`}>
      <Card className="overflow-hidden border-zinc-200 bg-white shadow-sm dark:border-zinc-900 dark:bg-zinc-950">
        <CardContent className="flex h-[calc(100vh-5.5rem)] flex-col p-0">
          <div ref={viewportRef} className="flex-1 space-y-4 overflow-auto px-4 py-4 md:px-5">
            {historyLoading && (
              <div className="flex max-w-3xl items-center gap-2 rounded-2xl border border-zinc-200 bg-zinc-50 p-4 text-sm text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
                <LoaderCircle size={14} className="animate-spin" />
                Loading your conversation...
              </div>
            )}
            {!historyLoading && messages.length === 1 && (
              <div className="mx-auto max-w-2xl px-4 py-8 text-center">
                <p className="text-2xl font-semibold tracking-tight text-zinc-950 dark:text-white">
                  Ask about your PDFs or research
                </p>
              </div>
            )}
            {messages.map((msg) => {
              const groupedSources = groupSources(msg.sources ?? []);
              return (
                <article
                  key={msg.id}
                  className={`max-w-3xl rounded-2xl border p-4 text-sm ${
                    msg.role === "user"
                      ? "ml-auto border-zinc-900 bg-zinc-900 text-white dark:border-zinc-700 dark:bg-zinc-100 dark:text-zinc-950"
                      : "border-zinc-200 bg-white text-zinc-900 dark:border-zinc-800 dark:bg-zinc-950 dark:text-white"
                  }`}
                >
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.12em] opacity-70">
                      {msg.role === "user" ? <User2 size={13} /> : <Bot size={13} />}
                      {msg.role === "user" ? "You" : "Assistant"}
                    </p>
                    {msg.role === "ai" && (
                      <button
                        type="button"
                        onClick={() => void copyMessage(msg.content)}
                        className="inline-flex items-center gap-1 rounded-full border border-zinc-200 px-2.5 py-1 text-[11px] text-zinc-600 transition hover:text-zinc-950 dark:border-zinc-800 dark:text-zinc-400 dark:hover:text-white"
                      >
                        <Copy size={11} />
                        Copy
                      </button>
                    )}
                  </div>
                  {msg.role === "ai" ? (
                    <MarkdownMessage content={msg.content} />
                  ) : (
                    <p className="leading-7">{msg.content}</p>
                  )}
                  {msg.role === "ai" && msg.sources && msg.sources.length > 0 && (
                    <div className="mt-5 space-y-4 rounded-2xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900">
                      <p className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-zinc-500">
                        <FileStack size={12} />
                        References
                      </p>
                      <SourceBlock title="From PDF" items={groupedSources.pdf} />
                      <SourceBlock title="From arXiv" items={groupedSources.arxiv} />
                      <SourceBlock title="Related Resources" items={groupedSources.resources} />
                    </div>
                  )}
                </article>
              );
            })}
            {loading && (
              <div className="flex max-w-3xl items-start gap-3 rounded-2xl border border-zinc-200 bg-zinc-50 p-4 text-sm text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
                <LoaderCircle size={14} className="mt-1 animate-spin" />
                <div className="space-y-2">
                  <p>Thinking through your question...</p>
                </div>
              </div>
            )}
          </div>

          <div className="border-t border-zinc-200 bg-white px-4 py-3 dark:border-zinc-900 dark:bg-zinc-950 md:px-5">
            <div className="mx-auto max-w-3xl space-y-3">
              {error && (
                <div className="flex items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300">
                  <span>{error}</span>
                  <button
                    type="button"
                    onClick={retryLastQuestion}
                    className="inline-flex items-center gap-2 text-xs font-medium"
                  >
                    <RefreshCcw size={13} />
                    Retry
                  </button>
                </div>
              )}
              <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900">
                <textarea
                  className="min-h-[52px] max-h-32 w-full resize-none border-0 bg-transparent px-0 py-0 text-[15px] leading-6 text-zinc-950 placeholder:text-zinc-500 focus:outline-none dark:text-white"
                  placeholder="Ask about your PDFs or latest research..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  disabled={loading}
                />
                <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                  <label className="text-xs text-zinc-500">
                    Focus document
                    <select
                      className="mt-1 block w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-950 dark:border-zinc-700 dark:bg-zinc-950 dark:text-white md:w-72"
                      value={selectedDocumentId}
                      onChange={(e) =>
                        setSelectedDocumentId(e.target.value === "all" ? "all" : Number(e.target.value))
                      }
                    >
                      <option value="all">All documents</option>
                      {documents.map((document) => (
                        <option key={document.id} value={document.id}>
                          #{document.id} {document.filename}
                        </option>
                      ))}
                    </select>
                  </label>
                  <Button
                    type="button"
                    onClick={() => void handleSubmitQuestion()}
                    className="h-10 gap-2 rounded-xl px-4"
                    disabled={loading || input.trim().length === 0}
                  >
                    <SendHorizontal size={15} />
                    {loading ? "Thinking..." : "Ask"}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {showSidebar && <Card className="h-fit border-zinc-200 bg-white shadow-sm dark:border-zinc-900 dark:bg-zinc-950">
        <CardContent className="space-y-3 p-4">
          <p className="text-sm font-semibold text-zinc-950 dark:text-white">Recent documents</p>
          {latestDocuments.length === 0 && (
            <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-4 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              Upload a PDF to start asking questions about it.
            </div>
          )}
          {latestDocuments.map((document) => (
            <div
              key={document.id}
              className="rounded-2xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <p className="text-sm font-semibold text-zinc-950 dark:text-white">{document.filename}</p>
              <p className="mt-1 text-xs text-zinc-500">Document #{document.id}</p>
              <p className="mt-3 line-clamp-4 text-sm text-zinc-600 dark:text-zinc-400">
                {cleanPreview(document.content_preview, 180)}
              </p>
            </div>
          ))}
        </CardContent>
      </Card>}
    </div>
  );
}
