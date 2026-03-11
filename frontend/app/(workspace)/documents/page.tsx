"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, LoaderCircle, RefreshCcw, Trash2 } from "lucide-react";
import { useToast } from "@/components/toast-provider";
import { WorkspaceHeader } from "@/components/workspace-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cleanPreview, uniqueLatestDocuments } from "@/lib/document-display";
import { deleteDocument, listDocuments, type DocumentRecord } from "@/lib/api";

export default function DocumentsPage() {
  const { toast } = useToast();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadDocuments() {
      try {
        const rows = await listDocuments();
        if (!active) {
          return;
        }
        const latestDocuments = uniqueLatestDocuments(rows);
        setDocuments(latestDocuments);
        setSelectedId(latestDocuments[0]?.id ?? null);
        setSuccess("Documents loaded successfully.");
        toast({
          variant: "info",
          title: "Documents loaded",
          description: `${latestDocuments.length} document(s) are available.`
        });
      } catch (loadError) {
        if (!active) {
          return;
        }
        setSuccess(null);
        setError(loadError instanceof Error ? loadError.message : "Could not load documents.");
        toast({
          variant: "error",
          title: "Document load failed",
          description:
            loadError instanceof Error ? loadError.message : "Could not load documents."
        });
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadDocuments();
    return () => {
      active = false;
    };
  }, []);

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedId) ?? null,
    [documents, selectedId]
  );

  const handleDelete = async (documentId: number) => {
    setDeletingId(documentId);
    setError(null);
    setSuccess(null);

    try {
      await deleteDocument(documentId);
      const nextDocuments = documents.filter((document) => document.id !== documentId);
      setDocuments(nextDocuments);
      setSelectedId(nextDocuments[0]?.id ?? null);
      setSuccess(`Deleted document #${documentId} successfully.`);
      toast({
        variant: "success",
        title: "Document deleted",
        description: `Document #${documentId} was removed from the workspace.`
      });
    } catch (deleteError) {
      setSuccess(null);
      setError(deleteError instanceof Error ? deleteError.message : "Delete failed.");
      toast({
        variant: "error",
        title: "Delete failed",
        description: deleteError instanceof Error ? deleteError.message : "Delete failed."
      });
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <>
      <WorkspaceHeader
        eyebrow="Library"
        title="Document Manager"
        subtitle="Inspect indexed files, review metadata, and remove documents from the workspace."
      />

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <Card className="shadow-panel border-zinc-800 bg-zinc-950/80">
          <CardHeader>
            <CardTitle>Uploaded Documents</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              A clean inventory of the knowledge sources currently indexed.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading && (
              <div className="flex items-center gap-2 rounded-[1.5rem] border border-zinc-800 bg-zinc-900/60 p-4 text-sm text-muted-foreground">
                <LoaderCircle size={14} className="animate-spin" />
                Loading documents...
              </div>
            )}
            {!loading && documents.length === 0 && (
              <div className="rounded-[1.5rem] border border-zinc-800 bg-zinc-900/60 p-4 text-sm text-muted-foreground">
                No documents found.
              </div>
            )}
            {documents.map((document) => (
              <button
                key={document.id}
                type="button"
                onClick={() => setSelectedId(document.id)}
                className={`w-full rounded-[1.5rem] border p-4 text-left transition ${
                  selectedId === document.id
                    ? "border-cyan-500/40 bg-cyan-500/10"
                    : "border-zinc-800 bg-zinc-900/60 hover:border-zinc-700 hover:bg-zinc-900"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{document.filename}</p>
                    <p className="mt-1 text-xs text-muted-foreground">Document #{document.id}</p>
                  </div>
                  <span className="rounded-full border border-zinc-800 bg-zinc-950 px-2.5 py-1 text-xs text-muted-foreground">
                    {new Date(document.created_at).toLocaleDateString()}
                  </span>
                </div>
                <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">
                  {cleanPreview(document.content_preview, 180)}
                </p>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card className="shadow-panel border-zinc-800 bg-zinc-950/80">
          <CardHeader>
            <CardTitle>Metadata</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              View reference details and manage individual documents.
            </p>
          </CardHeader>
          <CardContent>
            {error && (
              <div className="mb-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200">
                {error}
              </div>
            )}
            {success && (
              <div className="mb-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200">
                {success}
              </div>
            )}

            {!selectedDocument && (
              <div className="rounded-[1.75rem] border border-zinc-800 bg-zinc-900/60 p-6 text-sm text-muted-foreground">
                Select a document to inspect its metadata.
              </div>
            )}

            {selectedDocument && (
              <div className="space-y-4">
                <div className="rounded-[1.75rem] border border-zinc-800 bg-zinc-900/60 p-5">
                  <div className="flex items-start gap-3">
                    <span className="grid h-11 w-11 place-items-center rounded-2xl bg-primary/10 text-primary">
                      <FileText size={18} />
                    </span>
                    <div>
                      <p className="text-lg font-semibold">{selectedDocument.filename}</p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Document #{selectedDocument.id}
                      </p>
                    </div>
                  </div>
                  <dl className="mt-5 grid gap-4 sm:grid-cols-2">
                    <div className="rounded-2xl bg-zinc-950 p-4">
                      <dt className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                        Created
                      </dt>
                      <dd className="mt-2 text-sm font-medium">
                        {new Date(selectedDocument.created_at).toLocaleString()}
                      </dd>
                    </div>
                    <div className="rounded-2xl bg-zinc-950 p-4">
                      <dt className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                        Owner
                      </dt>
                      <dd className="mt-2 text-sm font-medium">User #{selectedDocument.user_id}</dd>
                    </div>
                  </dl>
                  <div className="mt-4 rounded-2xl bg-zinc-950 p-4">
                    <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                      Content preview
                    </p>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      {cleanPreview(selectedDocument.content_preview, 500)}
                    </p>
                  </div>
                </div>

                <Button
                  variant="secondary"
                  className="w-full gap-2 rounded-2xl"
                  onClick={() => void handleDelete(selectedDocument.id)}
                  disabled={deletingId === selectedDocument.id}
                >
                  {deletingId === selectedDocument.id ? (
                    <LoaderCircle size={15} className="animate-spin" />
                  ) : (
                    <Trash2 size={15} />
                  )}
                  Delete Document
                </Button>
                {error && (
                  <Button
                    variant="ghost"
                    className="w-full gap-2 rounded-2xl"
                    onClick={() => window.location.reload()}
                  >
                    <RefreshCcw size={15} />
                    Retry
                  </Button>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
