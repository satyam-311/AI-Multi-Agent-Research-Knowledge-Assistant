"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { LoaderCircle } from "lucide-react";
import { getAuthSession } from "@/lib/api";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;

    async function verify() {
      const session = getAuthSession();
      if (!session) {
        router.replace(`/login?next=${encodeURIComponent(pathname ?? "/dashboard")}`);
        return;
      }
      if (active) {
        setReady(true);
      }
    }

    void verify();
    return () => {
      active = false;
    };
  }, [pathname, router]);

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
