import { Brain, FileSearch, Layers, Zap } from "lucide-react";
import { ChatPanel } from "@/components/chat-panel";
import { Sidebar } from "@/components/sidebar";
import { UploadPanel } from "@/components/upload-panel";
import { Card, CardContent } from "@/components/ui/card";

const stages = [
  { title: "Document Processing Agent", icon: FileSearch, status: "Ready" },
  { title: "Embedding Agent", icon: Layers, status: "Ready" },
  { title: "Retrieval Agent", icon: Zap, status: "Ready" },
  { title: "Answer Generation Agent", icon: Brain, status: "Ready" }
];

export function DashboardShell() {
  return (
    <main className="min-h-screen p-4 md:p-8">
      <div className="mx-auto grid max-w-7xl gap-4 md:grid-cols-[18rem_1fr]">
        <Sidebar />
        <section className="space-y-4">
          <Card className="bg-gradient-to-r from-blue-600 to-cyan-500 text-white">
            <CardContent className="flex flex-col gap-1 py-8">
              <p className="text-sm uppercase tracking-[0.2em] text-white/80">AI Workspace</p>
              <h1 className="text-2xl font-semibold md:text-3xl">
                AI Multi-Agent Research Knowledge Assistant
              </h1>
              <p className="text-sm text-white/90">
                Upload PDFs, retrieve relevant context, and generate grounded answers.
              </p>
            </CardContent>
          </Card>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {stages.map((item) => (
              <Card key={item.title}>
                <CardContent className="flex items-center justify-between py-4">
                  <div>
                    <p className="text-xs text-muted-foreground">{item.status}</p>
                    <p className="text-sm font-semibold">{item.title}</p>
                  </div>
                  <item.icon size={18} className="text-primary" />
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid gap-4 xl:grid-cols-[22rem_1fr]">
            <UploadPanel />
            <ChatPanel />
          </div>
        </section>
      </div>
    </main>
  );
}
