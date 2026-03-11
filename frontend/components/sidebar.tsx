import { Bot, Database, FileText, LayoutDashboard, MessageSquare } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const navItems = [
  { icon: LayoutDashboard, label: "Dashboard", active: true },
  { icon: FileText, label: "Documents", active: false },
  { icon: MessageSquare, label: "Conversations", active: false },
  { icon: Database, label: "Vector Store", active: false },
  { icon: Bot, label: "Agents", active: false }
];

export function Sidebar() {
  return (
    <aside className="w-full rounded-3xl border bg-white/75 p-5 shadow-glow md:w-72">
      <div className="mb-8 flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-500 text-white">
          <Bot size={18} />
        </div>
        <div>
          <p className="text-sm font-semibold">Research Assistant</p>
          <p className="text-xs text-muted-foreground">Multi-Agent RAG</p>
        </div>
      </div>

      <Badge className="mb-5">Prototype v0.1</Badge>

      <nav className="space-y-2">
        {navItems.map((item) => (
          <button
            key={item.label}
            className={cn(
              "flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm transition-colors",
              item.active ? "bg-white text-foreground shadow-sm" : "text-muted-foreground hover:bg-white/70"
            )}
          >
            <item.icon size={16} />
            {item.label}
          </button>
        ))}
      </nav>
    </aside>
  );
}
