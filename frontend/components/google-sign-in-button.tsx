"use client";

import { LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/components/auth-provider";

export function GoogleSignInButton({
  onSuccess
}: {
  onSuccess?: () => void;
}) {
  const { signInWithGoogle, loading, error } = useAuth();

  const handleClick = async () => {
    try {
      await signInWithGoogle();
      onSuccess?.();
    } catch {
      return;
    }
  };

  return (
    <div className="space-y-3">
      <Button
        type="button"
        variant="secondary"
        className="h-12 w-full gap-3 rounded-[1.25rem] border border-zinc-800 bg-zinc-900 text-white hover:bg-zinc-800"
        onClick={() => void handleClick()}
        disabled={loading}
      >
        {loading ? (
          <LoaderCircle size={16} className="animate-spin" />
        ) : (
          <span className="grid h-6 w-6 place-items-center rounded-full bg-white text-[11px] font-bold text-slate-900">
            G
          </span>
        )}
        Sign in with Google
      </Button>
      {error && (
        <div className="rounded-2xl border border-rose-900/40 bg-rose-950/30 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}
    </div>
  );
}
