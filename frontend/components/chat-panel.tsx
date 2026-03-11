import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function ChatPanel() {
  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Ask Your Documents</CardTitle>
        <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs text-muted-foreground">
          <Sparkles size={14} />
          llama3
        </div>
      </CardHeader>
      <CardContent className="flex h-[28rem] flex-col">
        <div className="mb-4 flex-1 space-y-3 overflow-auto rounded-2xl bg-slate-50/80 p-4">
          <div className="max-w-[90%] rounded-2xl bg-white p-3 text-sm shadow-sm">
            Upload documents, then ask questions to start research chat.
          </div>
          <div className="ml-auto max-w-[90%] rounded-2xl bg-primary p-3 text-sm text-primary-foreground">
            What are the key findings in section 3?
          </div>
        </div>
        <div className="flex gap-2">
          <Input placeholder="Ask a question about uploaded PDFs..." />
          <Button>Send</Button>
        </div>
      </CardContent>
    </Card>
  );
}
