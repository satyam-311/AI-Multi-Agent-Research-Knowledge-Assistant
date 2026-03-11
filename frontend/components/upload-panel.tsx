import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function UploadPanel() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload Knowledge PDFs</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/80 p-8 text-center">
          <Upload className="mx-auto mb-3 text-muted-foreground" />
          <p className="text-sm font-medium">Drag and drop PDF files here</p>
          <p className="mt-1 text-xs text-muted-foreground">Up to 20MB per file</p>
        </div>
        <Button className="w-full">Select PDF</Button>
      </CardContent>
    </Card>
  );
}
