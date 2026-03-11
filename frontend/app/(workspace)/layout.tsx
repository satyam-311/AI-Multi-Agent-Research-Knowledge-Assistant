import { AuthGuard } from "@/components/auth-guard";
import { AppSidebar } from "@/components/app-sidebar";

export default function WorkspaceLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <AuthGuard>
      <main className="min-h-screen p-4 md:p-6">
        <div className="mx-auto grid max-w-7xl gap-4 md:grid-cols-[290px_1fr]">
          <AppSidebar />
          <section className="space-y-4">{children}</section>
        </div>
      </main>
    </AuthGuard>
  );
}
