"use client";

export function ThemeToggle() {
  return (
    <button
      type="button"
      disabled
      className="inline-flex h-10 items-center justify-center rounded-2xl border bg-card/80 px-3 text-muted-foreground opacity-70"
      aria-label="Dark theme enabled"
    >
      Dark
    </button>
  );
}
