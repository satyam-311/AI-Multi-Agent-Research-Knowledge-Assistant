"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, FileUp, LoaderCircle, RefreshCw, XCircle } from "lucide-react";
import { useToast } from "@/components/toast-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { uploadDocument } from "@/lib/api";

type UploadState = "idle" | "uploading" | "done" | "error";

export function DocumentUploadView() {
  const { toast } = useToast();
  const [dragging, setDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [status, setStatus] = useState<UploadState>("idle");
  const [isUploading, setIsUploading] = useState(false);
  const [detail, setDetail] = useState("Waiting for PDF");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [uploadedInfo, setUploadedInfo] = useState<{ documentId: number; chunks: number } | null>(
    null
  );

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

  const onSelectFile = (file?: File) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setSelectedFile(null);
      setStatus("error");
      setError("Only PDF files can be uploaded.");
      setSuccess(null);
      setUploadedInfo(null);
      setProgress(0);
      setDetail("Unsupported file type");
      toast({
        variant: "error",
        title: "Upload blocked",
        description: "Only PDF files are supported."
      });
      return;
    }

    setSelectedFile(file);
    setStatus("idle");
    setError(null);
    setSuccess(null);
    setUploadedInfo(null);
    setProgress(0);
    setDetail("Ready to upload");
  };

  const onUpload = async () => {
    if (!selectedFile) {
      setStatus("error");
      setError("Choose a PDF before uploading.");
      setSuccess(null);
      setDetail("No file selected");
      toast({
        variant: "error",
        title: "No file selected",
        description: "Choose a PDF before uploading."
      });
      return;
    }

    setStatus("uploading");
    setIsUploading(true);
    setError(null);
    setSuccess(null);
    setProgress(0);
    setDetail("Preparing your document");

    try {
      const response = await uploadDocument(selectedFile, {
        onProgress: setProgress
      });
      setStatus("done");
      setProgress(100);
      setUploadedInfo({
        documentId: response.document_id,
        chunks: response.chunks_created
      });
      setDetail(`Ready to chat with ${response.filename}`);
      setSuccess(`Uploaded ${response.filename} successfully.`);
      toast({
        variant: "success",
        title: "Document uploaded",
        description: `${response.filename} is ready for chat.`
      });
    } catch (uploadError) {
      setStatus("error");
      setUploadedInfo(null);
      setProgress(0);
      setDetail("Upload failed");
      setSuccess(null);
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed.");
      toast({
        variant: "error",
        title: "Upload failed",
        description:
          uploadError instanceof Error ? uploadError.message : "The PDF could not be uploaded."
      });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Card className="shadow-panel overflow-hidden border-zinc-800 bg-zinc-950/80">
      <CardHeader className="border-b border-zinc-800/80">
        <CardTitle>Document Upload</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <label
          className={`block rounded-[2rem] border-2 border-dashed p-8 text-center transition-all ${
            dragging
              ? "border-cyan-400 bg-cyan-500/10 shadow-lg shadow-cyan-950/30"
              : "border-zinc-800 bg-zinc-900/60 hover:border-zinc-700 hover:bg-zinc-900"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            onSelectFile(e.dataTransfer.files?.[0]);
          }}
        >
          <input
            id="document-upload-input"
            type="file"
            className="hidden"
            accept=".pdf"
            disabled={isUploading}
            onChange={(e) => onSelectFile(e.target.files?.[0] ?? undefined)}
          />
          <FileUp className="mx-auto mb-3 text-primary" />
          <p className="text-sm font-semibold">Drag and drop PDF files</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Click to browse or drop a research paper, report, or notes bundle
          </p>
        </label>

        <div className="rounded-[1.75rem] border border-zinc-800 bg-zinc-900/70 p-4">
          <div className="flex items-center justify-between gap-4">
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Current status
            </p>
            <span className="text-xs font-medium text-muted-foreground">{progress}%</span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-zinc-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-500 via-sky-500 to-emerald-400 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="mt-2 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">{selectedFile?.name ?? "No file selected"}</p>
              <p className="text-xs text-muted-foreground">{detail}</p>
              {uploadedInfo && (
                <p className="mt-1 text-xs text-emerald-700">
                  Document #{uploadedInfo.documentId} is ready.
                </p>
              )}
              {success && <p className="mt-1 text-xs text-emerald-700">{success}</p>}
              {error && <p className="mt-1 text-xs text-rose-600">{error}</p>}
            </div>
            {status === "idle" && <XCircle size={18} className="text-muted-foreground" />}
            {status === "uploading" && (
              <LoaderCircle size={18} className="animate-spin text-primary" />
            )}
            {status === "done" && <CheckCircle2 size={18} className="text-emerald-600" />}
            {status === "error" && <XCircle size={18} className="text-rose-600" />}
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-[1fr_auto]">
          <Button
            className="w-full"
            onClick={onUpload}
            disabled={isUploading || selectedFile === null}
          >
            {isUploading ? "Uploading..." : "Upload PDF"}
          </Button>
          {status === "error" && (
            <Button
              variant="secondary"
              className="gap-2"
              onClick={onUpload}
              disabled={selectedFile === null || isUploading}
            >
              <RefreshCw size={15} />
              Retry
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
