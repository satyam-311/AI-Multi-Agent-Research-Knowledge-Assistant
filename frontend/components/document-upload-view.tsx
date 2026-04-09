"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, FileUp, LoaderCircle, RefreshCw, XCircle } from "lucide-react";
import { useToast } from "@/components/toast-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { listDocuments, uploadDocument } from "@/lib/api";

type UploadState = "idle" | "uploading" | "processing" | "ready" | "error";

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
  const pollIntervalRef = useRef<number | null>(null);

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
    return () => {
      if (pollIntervalRef.current !== null) {
        window.clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

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

  const startProcessingPoll = (documentId: number, filename: string) => {
    if (pollIntervalRef.current !== null) {
      window.clearInterval(pollIntervalRef.current);
    }

    let attempts = 0;
    pollIntervalRef.current = window.setInterval(async () => {
      attempts += 1;
      try {
        const documents = await listDocuments();
        const document = documents.find((item) => item.id === documentId);
        if (!document) {
          return;
        }

        const preview = (document.content_preview ?? "").trim();
        const isFailed = preview.toLowerCase().startsWith("processing failed:");
        const isReady = preview.length > 0 && preview !== "Processing document...";

        if (isFailed) {
          if (pollIntervalRef.current !== null) {
            window.clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          setStatus("error");
          setProgress(0);
          setDetail("Processing failed");
          setError(preview);
          return;
        }

        if (isReady) {
          if (pollIntervalRef.current !== null) {
            window.clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          setStatus("ready");
          setProgress(100);
          setDetail(`Ready to chat with ${filename}`);
          setSuccess(`Uploaded ${filename} successfully.`);
          toast({
            variant: "success",
            title: "Document ready",
            description: `${filename} is indexed and ready for chat.`
          });
          return;
        }

        if (attempts >= 45) {
          if (pollIntervalRef.current !== null) {
            window.clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          setStatus("processing");
          setDetail("Still processing. You can wait a bit and refresh later.");
        }
      } catch (pollError) {
        console.error("Upload processing poll failed", pollError);
      }
    }, 2000);
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
      console.info("Upload API response", response);
      setUploadedInfo({
        documentId: response.document_id,
        chunks: response.chunks_created
      });
      if (response.processing) {
        setStatus("processing");
        setProgress(100);
        setDetail("Processing your document");
        setSuccess(null);
        startProcessingPoll(response.document_id, response.filename);
      } else {
        setStatus("ready");
        setProgress(100);
        setDetail(`Ready to chat with ${response.filename}`);
        setSuccess(`Uploaded ${response.filename} successfully.`);
        toast({
          variant: "success",
          title: "Document uploaded",
          description: `${response.filename} is ready for chat.`
        });
      }
    } catch (uploadError) {
      console.error("Upload failed", uploadError);
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
    <Card className="overflow-hidden border-zinc-200 bg-white shadow-sm dark:border-zinc-900 dark:bg-zinc-950">
      <CardHeader className="border-b border-zinc-200 dark:border-zinc-900">
        <CardTitle>Document Upload</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <label
          htmlFor="document-upload-input"
          className={`block rounded-3xl border-2 border-dashed p-8 text-center transition-all ${
            dragging
              ? "border-zinc-400 bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900"
              : "border-zinc-300 bg-zinc-50 hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700"
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

        <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center justify-between gap-4">
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Current status
            </p>
            <span className="text-xs font-medium text-muted-foreground">{progress}%</span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
            <div
              className="h-full rounded-full bg-zinc-900 transition-all dark:bg-white"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="mt-2 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">{selectedFile?.name ?? "No file selected"}</p>
              <p className="text-xs text-muted-foreground">{detail}</p>
              {uploadedInfo && (
                <p className="mt-1 text-xs text-emerald-700">
                  Document #{uploadedInfo.documentId}{" "}
                  {status === "ready" ? "is ready." : "is processing."}
                </p>
              )}
              {success && <p className="mt-1 text-xs text-emerald-700">{success}</p>}
              {error && <p className="mt-1 text-xs text-rose-600">{error}</p>}
            </div>
    {status === "idle" && <XCircle size={18} className="text-muted-foreground" />}
            {(status === "uploading" || status === "processing") && (
              <LoaderCircle size={18} className="animate-spin text-primary" />
            )}
            {status === "ready" && <CheckCircle2 size={18} className="text-emerald-600" />}
            {status === "error" && <XCircle size={18} className="text-rose-600" />}
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-[1fr_auto]">
          <Button
            className="w-full"
            onClick={onUpload}
            disabled={isUploading || status === "processing" || selectedFile === null}
          >
            {status === "uploading"
              ? "Uploading..."
              : status === "processing"
                ? "Processing..."
                : "Upload PDF"}
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
