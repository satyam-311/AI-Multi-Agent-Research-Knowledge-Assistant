import { CheckCircle2, FileUp, LoaderCircle } from "lucide-react";
import { DocumentUploadView } from "@/components/document-upload-view";
import { WorkspaceHeader } from "@/components/workspace-header";

export default function UploadPage() {
  return (
    <div className="space-y-5">
      <WorkspaceHeader
        eyebrow="Ingestion"
        title="Document Upload"
        subtitle="A simple flow: upload the PDF, let it process, then start chatting."
      />
      <div className="grid gap-3 md:grid-cols-3">
        {[
          { label: "Upload", icon: FileUp },
          { label: "Processing", icon: LoaderCircle },
          { label: "Ready", icon: CheckCircle2 }
        ].map((step) => (
          <div
            key={step.label}
            className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-900 dark:bg-zinc-950"
          >
            <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-100 text-zinc-700 dark:bg-zinc-900 dark:text-zinc-200">
              <step.icon size={18} className={step.label === "Processing" ? "animate-spin" : ""} />
            </div>
            <p className="font-semibold text-zinc-950 dark:text-white">{step.label}</p>
          </div>
        ))}
      </div>
      <DocumentUploadView />
    </div>
  );
}
