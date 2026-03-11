import Link from "next/link";
import { ArrowRight, Bot, FileSearch2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const highlights = [
  {
    title: "Upload PDFs",
    description: "Ingest research papers, reports, and meeting notes in seconds.",
    icon: FileSearch2
  },
  {
    title: "Multi-Agent RAG",
    description: "Processing, embeddings, retrieval, and answer generation agents.",
    icon: Bot
  },
  {
    title: "Grounded Answers",
    description: "Chat with context-backed responses and source references.",
    icon: Sparkles
  }
];

export default function LandingPage() {
  return (
    <main className="min-h-screen px-4 py-8 md:px-8 md:py-10">
      <section className="mx-auto max-w-6xl">
        <div className="glass mb-4 flex items-center justify-between rounded-3xl p-4">
          <p className="text-sm font-semibold">AI Multi-Agent Research Knowledge Assistant</p>
          <Link href="/login">
            <Button size="sm">Sign In</Button>
          </Link>
        </div>

        <div className="glass rounded-3xl p-8 md:p-12">
          <p className="mb-3 inline-flex rounded-full bg-white px-3 py-1 text-xs font-medium text-muted-foreground">
            Next.js + FastAPI + Ollama + Chroma
          </p>
          <h1 className="max-w-3xl text-4xl font-semibold leading-tight md:text-6xl">
            Research Faster With a Multi-Agent AI Workspace
          </h1>
          <p className="mt-4 max-w-2xl text-sm text-muted-foreground md:text-base">
            Upload documents, retrieve semantically relevant chunks, and ask deep questions with
            transparent sources.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/login">
              <Button size="lg" className="gap-2">
                Sign In <ArrowRight size={16} />
              </Button>
            </Link>
            <Link href="/login">
              <Button size="lg" variant="secondary">
                Open Workspace
              </Button>
            </Link>
          </div>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {highlights.map((item) => (
            <Card key={item.title} className="animate-slide-up">
              <CardContent className="py-6">
                <span className="mb-4 grid h-10 w-10 place-items-center rounded-2xl bg-slate-100 text-primary">
                  <item.icon size={18} />
                </span>
                <h2 className="text-base font-semibold">{item.title}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </main>
  );
}
