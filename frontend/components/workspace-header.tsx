import { Bell, Search } from "lucide-react";
import { Input } from "@/components/ui/input";

export function WorkspaceHeader({
  title,
  subtitle,
  eyebrow
}: {
  title: string;
  subtitle: string;
  eyebrow?: string;
}) {
  return (
    <header className="glass shadow-panel flex flex-col gap-4 rounded-[2rem] border-zinc-800 bg-zinc-950/70 p-5 md:flex-row md:items-center md:justify-between">
      <div>
        {eyebrow && (
          <p className="mb-2 text-xs uppercase tracking-[0.18em] text-cyan-300/80">
            {eyebrow}
          </p>
        )}
        <h1 className="text-balance text-xl font-semibold md:text-3xl">{title}</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{subtitle}</p>
      </div>
      <div className="flex items-center gap-2">
        <div className="relative w-full md:w-64">
          <Search
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input className="border-zinc-800 bg-zinc-900 pl-9" placeholder="Search documents or chats" />
        </div>
        <button className="grid h-10 w-10 place-items-center rounded-2xl border border-zinc-800 bg-zinc-900/80 transition hover:bg-zinc-900">
          <Bell size={16} />
        </button>
      </div>
    </header>
  );
}
