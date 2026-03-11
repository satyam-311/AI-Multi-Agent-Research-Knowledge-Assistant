"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  Bot,
  Copy,
  FileStack,
  Hash,
  LoaderCircle,
  RefreshCcw,
  SendHorizontal,
  Sparkles,
  User2
} from "lucide-react";
import { MarkdownMessage } from "@/components/markdown-message";
import { useToast } from "@/components/toast-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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

export function ChatWorkspace() {
  const { toast } = useToast();
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | "all">("all");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState("");
  const viewportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    viewportRef.current?.scrollTo({
      top: viewportRef.current.scrollHeight,
      behavior: "smooth"
    });
  }, [messages, loading]);

  useEffect(() => {
    if (!error && !success) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setError(null);
      setSuccess(null);
    }, 5000);

    return () => window.clearTimeout(timeout);
  }, [error, success]);

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
        setSuccess("Conversation ready.");
      } catch (loadError) {
        if (!active) return;
        setSuccess(null);
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

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
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
    setSuccess(null);

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
      setSuccess("Answer generated successfully.");
      toast({
        variant: "success",
        title: "Answer ready",
        description: response.sources.length
          ? `Answered with ${response.sources.length} source reference(s).`
          : "Answer generated successfully."
      });
    } catch (submitError) {
      setSuccess(null);
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

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_300px]">
      <Card className="shadow-panel overflow-hidden border-zinc-800 bg-zinc-950/85">
        <CardHeader className="flex flex-col gap-4 border-b border-border/70 pb-4 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle>Chat With Your Documents</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              Ask clear questions and review the supporting references.
            </p>
          </div>
          <span className="inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100">
            <Sparkles size={13} />
            document assistant
          </span>
        </CardHeader>
        <CardContent className="space-y-4 p-0">
          <div className="flex flex-col gap-3 border-b border-border/70 px-6 py-4 md:flex-row md:items-end md:justify-between">
            <label className="text-xs text-muted-foreground">
              Focus document
              <select
                className="mt-1 block w-full rounded-2xl border border-zinc-800 bg-zinc-900 px-3 py-2.5 text-sm text-foreground md:w-80"
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
            <div className="space-y-1 text-right">
              {success && <p className="text-sm text-emerald-600">{success}</p>}
              {error && <p className="text-sm text-rose-600">{error}</p>}
              {error && (
                <button
                  type="button"
                  onClick={retryLastQuestion}
                  className="inline-flex items-center gap-2 text-xs text-cyan-300 transition hover:text-cyan-200"
                >
                  <RefreshCcw size={13} />
                  Retry last question
                </button>
              )}
            </div>
          </div>

          <div
            ref={viewportRef}
            className="h-[62vh] space-y-4 overflow-auto bg-zinc-950/40 px-4 py-5 md:px-6"
          >
            {historyLoading && (
              <div className="flex max-w-[92%] items-center gap-2 rounded-[1.75rem] bg-card p-4 text-sm shadow-sm">
                <LoaderCircle size={14} className="animate-spin text-primary" />
                Loading your conversation...
              </div>
            )}
            {messages.map((msg) => (
              <article
                key={msg.id}
                className={`animate-slide-up max-w-[92%] rounded-[1.75rem] p-4 text-sm ${
                  msg.role === "user"
                    ? "ml-auto border border-cyan-500/20 bg-gradient-to-br from-cyan-500 to-sky-500 text-primary-foreground shadow-lg shadow-cyan-950/40"
                    : "border border-zinc-800 bg-zinc-900 text-card-foreground shadow-sm"
                }`}
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="flex items-center gap-2 text-xs opacity-80">
                    {msg.role === "user" ? <User2 size={13} /> : <Bot size={13} />}
                    {msg.role === "user" ? "You" : "Assistant"}
                  </p>
                  {msg.role === "ai" && (
                    <button
                      type="button"
                      onClick={() => void copyMessage(msg.content)}
                      className="inline-flex items-center gap-1 rounded-full border border-zinc-700 bg-zinc-950/60 px-2.5 py-1 text-[11px] text-zinc-300 transition hover:border-zinc-600 hover:text-white"
                    >
                      <Copy size={11} />
                      Copy
                    </button>
                  )}
                </div>
                {msg.role === "ai" ? (
                  <MarkdownMessage content={msg.content} />
                ) : (
                  <p className="leading-6">{msg.content}</p>
                )}
                {msg.role === "ai" && msg.sources && msg.sources.length > 0 && (
                  <div className="mt-4 rounded-2xl border border-zinc-800 bg-zinc-950/80 p-3">
                    <p className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-zinc-500">
                      <FileStack size={12} />
                      Sources
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {dedupeSources(msg.sources).map((source, index) => (
                        <span
                          key={`${msg.id}-${source}-${index}`}
                          className="inline-flex items-center gap-1 rounded-full border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-xs text-zinc-300"
                        >
                          <Hash size={11} />
                          {source}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </article>
            ))}
            {loading && (
              <div className="flex max-w-[92%] items-start gap-3 rounded-[1.75rem] border border-zinc-800 bg-zinc-900 p-4 text-sm shadow-sm">
                <LoaderCircle size={14} className="mt-1 animate-spin text-primary" />
                <div className="space-y-2">
                  <p className="text-zinc-100">Thinking through your question...</p>
                  <div className="space-y-2">
                    <div className="h-2 w-40 animate-pulse rounded-full bg-zinc-800" />
                    <div className="h-2 w-64 animate-pulse rounded-full bg-zinc-800" />
                    <div className="h-2 w-52 animate-pulse rounded-full bg-zinc-800" />
                  </div>
                </div>
              </div>
            )}
          </div>

          <form onSubmit={submit} className="border-t border-border/70 bg-card/70 px-4 py-4 md:px-6">
            <div className="flex gap-2 rounded-[1.75rem] border border-zinc-800 bg-zinc-950/80 p-2">
              <Input
                className="border-0 bg-transparent"
                placeholder="Ask a question about uploaded PDFs..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={loading}
              />
              <Button
                type="submit"
                className="gap-2 rounded-2xl px-5"
                disabled={loading || input.trim().length === 0}
              >
                <SendHorizontal size={15} />
                {loading ? "Thinking..." : "Send"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card className="shadow-panel h-fit border-zinc-800 bg-zinc-950/80">
        <CardHeader>
          <CardTitle>Documents</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Your recent uploads appear here while you chat.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {documents.length === 0 && (
            <div className="rounded-[1.5rem] border border-zinc-800 bg-zinc-900/60 p-4 text-sm text-muted-foreground">
              Upload a PDF to start asking questions about it.
            </div>
          )}
          {documents.slice(0, 5).map((document) => (
            <div
              key={document.id}
              className="rounded-[1.5rem] border border-zinc-800 bg-zinc-900/60 p-4 transition hover:border-zinc-700"
            >
              <p className="text-sm font-semibold">{document.filename}</p>
              <p className="mt-1 text-xs text-muted-foreground">Document #{document.id}</p>
              <p className="mt-3 line-clamp-4 text-sm text-muted-foreground">
                {cleanPreview(document.content_preview, 180)}
              </p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
