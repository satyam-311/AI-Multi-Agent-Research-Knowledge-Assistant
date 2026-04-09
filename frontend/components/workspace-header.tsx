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
    <header className="rounded-2xl border border-zinc-200 bg-white px-5 py-4 shadow-sm dark:border-zinc-900 dark:bg-zinc-950">
      <div>
        {eyebrow && (
          <p className="mb-1.5 text-[11px] uppercase tracking-[0.18em] text-zinc-500">
            {eyebrow}
          </p>
        )}
        <h1 className="text-balance text-2xl font-semibold tracking-tight text-zinc-950 dark:text-white">
          {title}
        </h1>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-600 dark:text-zinc-400">
          {subtitle}
        </p>
      </div>
    </header>
  );
}
