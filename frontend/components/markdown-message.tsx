import { cn } from "@/lib/utils";

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function inlineMarkdown(value: string) {
  return value
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noreferrer">$1</a>'
    );
}

function markdownToHtml(source: string) {
  const escaped = escapeHtml(source).replace(/\r\n/g, "\n");
  const blocks = escaped.split(/\n{2,}/).filter(Boolean);

  return blocks
    .map((block) => {
      const trimmed = block.trim();
      if (trimmed.startsWith("```") && trimmed.endsWith("```")) {
        const content = trimmed.replace(/^```/, "").replace(/```$/, "").trim();
        return `<pre><code>${content}</code></pre>`;
      }

      const lines = trimmed.split("\n");
      if (lines.every((line) => /^[-*]\s+/.test(line))) {
        const items = lines
          .map((line) => line.replace(/^[-*]\s+/, ""))
          .map((line) => `<li>${inlineMarkdown(line)}</li>`)
          .join("");
        return `<ul>${items}</ul>`;
      }

      if (/^#{1,3}\s/.test(trimmed)) {
        const level = trimmed.match(/^#+/)?.[0].length ?? 1;
        const text = trimmed.replace(/^#{1,3}\s/, "");
        return `<h${level}>${inlineMarkdown(text)}</h${level}>`;
      }

      return `<p>${lines.map((line) => inlineMarkdown(line)).join("<br />")}</p>`;
    })
    .join("");
}

export function MarkdownMessage({
  content,
  className,
}: {
  content: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "space-y-3 text-sm leading-7 [&_a]:text-cyan-300 [&_a]:underline [&_code]:rounded-md [&_code]:bg-zinc-950 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:text-[0.92em] [&_h1]:text-lg [&_h1]:font-semibold [&_h2]:text-base [&_h2]:font-semibold [&_h3]:font-semibold [&_li]:ml-5 [&_li]:list-disc [&_pre]:overflow-x-auto [&_pre]:rounded-2xl [&_pre]:border [&_pre]:border-zinc-800 [&_pre]:bg-zinc-950 [&_pre]:p-4",
        className
      )}
      dangerouslySetInnerHTML={{ __html: markdownToHtml(content) }}
    />
  );
}
