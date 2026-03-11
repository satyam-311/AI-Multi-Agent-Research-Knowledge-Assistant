import { BrainCircuit, FileSearch, MessagesSquare } from "lucide-react";
import { ChatWorkspace } from "@/components/chat-workspace";
import { WorkspaceHeader } from "@/components/workspace-header";
import { Card, CardContent } from "@/components/ui/card";

const tips = [
  { icon: MessagesSquare, text: "Ask specific questions for better retrieval quality." },
  { icon: FileSearch, text: "Attach document IDs if you want focused context search." },
  { icon: BrainCircuit, text: "Answers include source references from indexed chunks." }
];

export default function ChatPage() {
  return (
    <>
      <WorkspaceHeader
        eyebrow="Conversation"
        title="AI Chat"
        subtitle="Ask questions and get ChatGPT-style grounded answers with source-backed references."
      />
      <ChatWorkspace />
      <Card className="h-fit">
        <CardContent className="grid gap-3 py-6 md:grid-cols-3">
          {tips.map((tip) => (
            <div key={tip.text} className="rounded-2xl bg-muted/40 p-3 text-sm text-muted-foreground">
              <p className="mb-1 inline-flex items-center gap-2 text-foreground">
                <tip.icon size={14} />
                Tip
              </p>
              {tip.text}
            </div>
          ))}
        </CardContent>
      </Card>
    </>
  );
}
