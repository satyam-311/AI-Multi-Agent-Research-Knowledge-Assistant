import { Layers3, ScanSearch, Sparkle } from "lucide-react";
import { DocumentUploadView } from "@/components/document-upload-view";
import { WorkspaceHeader } from "@/components/workspace-header";
import { Card, CardContent } from "@/components/ui/card";

const steps = [
  { title: "Extract PDF text", icon: ScanSearch },
  { title: "Chunk the content", icon: Layers3 },
  { title: "Generate embeddings", icon: Sparkle }
];

export default function UploadPage() {
  return (
    <>
      <WorkspaceHeader
        eyebrow="Ingestion"
        title="Document Upload"
        subtitle="Ingest PDFs, monitor upload progress, and prepare indexed context for question answering."
      />
      <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
        <DocumentUploadView />
        <Card>
          <CardContent className="space-y-4 py-6">
            <p className="text-sm font-semibold">Pipeline Steps</p>
            {steps.map((step) => (
              <div key={step.title} className="flex items-center gap-3 rounded-2xl bg-muted/40 p-3">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-card text-primary">
                  <step.icon size={16} />
                </span>
                <p className="text-sm">{step.title}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
