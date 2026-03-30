"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Bot, LoaderCircle } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams?.get("next") || "/dashboard";
  const { user, loading, error, signInWithEmail, signInWithGoogle, signUpWithEmail } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (user) {
      router.replace(nextPath);
    }
  }, [nextPath, router, user]);

  const handleEmailSignIn = async () => {
    await signInWithEmail(email.trim(), password);
  };

  const handleEmailSignUp = async () => {
    await signUpWithEmail(email.trim(), password);
  };

  const handleGoogleSignIn = async () => {
    await signInWithGoogle();
  };

  return (
    <main className="grid min-h-screen place-items-center bg-zinc-950 px-4 py-10">
      <Card className="w-full max-w-md border-zinc-800 bg-zinc-950/90 shadow-panel">
        <CardHeader className="space-y-5 text-center">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-3xl bg-gradient-to-br from-cyan-500 via-blue-500 to-teal-400 text-white shadow-lg shadow-cyan-500/30">
            <Bot size={22} />
          </div>
          <div>
            <CardTitle>AI Research Assistant</CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">
              Sign in with email and password or continue with Google to access your research workspace.
            </p>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-3">
            <label className="block text-left text-sm font-medium text-zinc-200" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              className="h-12 w-full rounded-2xl border border-zinc-800 bg-zinc-900 px-4 text-sm text-white outline-none transition focus:border-cyan-500"
              disabled={loading}
            />
          </div>

          <div className="space-y-3">
            <label
              className="block text-left text-sm font-medium text-zinc-200"
              htmlFor="password"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter your password"
              className="h-12 w-full rounded-2xl border border-zinc-800 bg-zinc-900 px-4 text-sm text-white outline-none transition focus:border-cyan-500"
              disabled={loading}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Button
              type="button"
              className="h-12 rounded-2xl bg-cyan-500 text-zinc-950 hover:bg-cyan-400"
              onClick={() => void handleEmailSignIn()}
              disabled={loading}
            >
              {loading ? <LoaderCircle size={16} className="animate-spin" /> : "Sign In"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              className="h-12 rounded-2xl border border-zinc-800 bg-zinc-900 text-white hover:bg-zinc-800"
              onClick={() => void handleEmailSignUp()}
              disabled={loading}
            >
              {loading ? <LoaderCircle size={16} className="animate-spin" /> : "Sign Up"}
            </Button>
          </div>

          <div className="flex items-center gap-3 text-xs uppercase tracking-[0.28em] text-zinc-500">
            <div className="h-px flex-1 bg-zinc-800" />
            <span>OR</span>
            <div className="h-px flex-1 bg-zinc-800" />
          </div>

          <Button
            type="button"
            variant="secondary"
            className="h-12 w-full gap-3 rounded-2xl border border-zinc-800 bg-zinc-900 text-white hover:bg-zinc-800"
            onClick={() => void handleGoogleSignIn()}
            disabled={loading}
          >
            {loading ? (
              <LoaderCircle size={16} className="animate-spin" />
            ) : (
              <span className="grid h-6 w-6 place-items-center rounded-full bg-white text-[11px] font-bold text-slate-900">
                G
              </span>
            )}
            Continue with Google
          </Button>

          {loading && !user && (
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 px-4 py-3 text-sm text-zinc-300">
              Completing secure sign-in...
            </div>
          )}

          {error && (
            <div className="rounded-2xl border border-rose-900/40 bg-rose-950/30 px-4 py-3 text-sm text-rose-200">
              {error}
            </div>
          )}

          <div className="text-center text-sm text-muted-foreground">
            <Link href="/" className="hover:text-zinc-200">
              Back to home
            </Link>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
