"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { LoaderCircle } from "lucide-react";
import { useAuth } from "@/components/auth-provider";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const { user, loading } = useAuth();

  useEffect(() => {
    if (loading) {
      return;
    }

    if (!user) {
      router.replace(`/login?next=${encodeURIComponent(pathname ?? "/dashboard")}`);
      return;
    }

    setReady(true);
  }, [loading, pathname, router, user]);

  if (!ready) {
    return (
      <main className="grid min-h-screen place-items-center p-6">
        <div className="flex items-center gap-3 rounded-3xl border border-zinc-800 bg-zinc-950/80 px-5 py-4 text-sm text-zinc-200">
          <LoaderCircle size={16} className="animate-spin text-cyan-400" />
          Checking your session...
        </div>
      </main>
    );
  }

  return <>{children}</>;
}
