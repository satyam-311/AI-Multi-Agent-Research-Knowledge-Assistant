import { AuthGuard } from "@/components/auth-guard";
import { AppSidebar } from "@/components/app-sidebar";

export default function WorkspaceLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <AuthGuard>
      <main className="min-h-screen bg-zinc-50 px-4 py-5 dark:bg-black md:px-6 md:py-6">
        <div className="mx-auto grid max-w-7xl gap-6 md:grid-cols-[220px_minmax(0,1fr)]">
          <AppSidebar />
          <section className="space-y-5">{children}</section>
        </div>
      </main>
    </AuthGuard>
  );
}
