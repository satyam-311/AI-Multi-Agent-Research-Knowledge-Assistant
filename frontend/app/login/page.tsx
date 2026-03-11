"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Bot, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getAuthSession, login, register, setAuthSession } from "@/lib/api";

type Mode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams?.get("next") || "/dashboard";
  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (getAuthSession()) {
      router.replace(nextPath);
    }
  }, [nextPath, router]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const session =
        mode === "login"
          ? await login({ email, password })
          : await register({ name, email, password });
      setAuthSession(session);
      router.replace(nextPath);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Authentication failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="grid min-h-screen place-items-center px-4 py-10">
      <Card className="w-full max-w-md border-zinc-800 bg-zinc-950/85 shadow-panel">
        <CardHeader className="space-y-4 text-center">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-3xl bg-gradient-to-br from-cyan-500 via-blue-500 to-teal-400 text-white shadow-lg shadow-cyan-500/30">
            <Bot size={22} />
          </div>
          <div>
            <CardTitle>{mode === "login" ? "Sign In" : "Create Account"}</CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">
              Use a local account to keep your uploads and chat history separate.
            </p>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-4">
            {mode === "register" && (
              <div className="space-y-2">
                <label className="text-sm text-zinc-300">Name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} required />
              </div>
            )}
            <div className="space-y-2">
              <label className="text-sm text-zinc-300">Email</label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm text-zinc-300">Password</label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                required
              />
            </div>
            {error && (
              <div className="rounded-2xl border border-rose-900/40 bg-rose-950/30 px-4 py-3 text-sm text-rose-200">
                {error}
              </div>
            )}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <>
                  <LoaderCircle size={15} className="animate-spin" /> Please wait
                </>
              ) : mode === "login" ? (
                "Sign In"
              ) : (
                "Create Account"
              )}
            </Button>
          </form>

          <div className="mt-5 text-center text-sm text-muted-foreground">
            {mode === "login" ? "Need an account?" : "Already have an account?"}{" "}
            <button
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError(null);
              }}
              className="font-medium text-cyan-300 hover:text-cyan-200"
            >
              {mode === "login" ? "Create one" : "Sign in"}
            </button>
          </div>

          <div className="mt-4 text-center text-sm text-muted-foreground">
            <Link href="/" className="hover:text-zinc-200">
              Back to home
            </Link>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
