import type { ChatHistoryRecord, DocumentRecord } from "@/lib/api";

const PREVIEW_NOISE_PATTERNS = [
  /\b20\d{2}\b/gi,
  /copyright held by the author\(s\)\.?/gi,
  /published by [^.]+/gi,
  /proceedings doi:[^.]+/gi,
  /series:[^.]+/gi,
  /issn:[^.]+/gi,
  /isbn:[^.]+/gi,
  /organized by [^.]+/gi,
  /publisher'?s note[^.]+/gi
];

const PREFERRED_PREVIEW_PATTERNS = [
  /(abstract[:\s].{80,500})/i,
  /(introduction[:\s].{80,500})/i,
  /(fake news detection using logistic regression method.{40,400})/i,
  /(logistic regression.{40,400})/i
];

export function cleanPreview(text: string, maxLength = 220): string {
  if (!text) {
    return "Preview unavailable.";
  }

  let normalized = text.replace(/\s+/g, " ").trim();
  for (const pattern of PREVIEW_NOISE_PATTERNS) {
    normalized = normalized.replace(pattern, " ");
  }
  normalized = normalized.replace(/\s+/g, " ").trim();

  for (const pattern of PREFERRED_PREVIEW_PATTERNS) {
    const match = normalized.match(pattern);
    if (match?.[1]) {
      normalized = match[1].trim();
      break;
    }
  }

  const sentenceMatches = normalized.match(/[A-Z][^.?!]{25,220}[.?!]/g);
  if (sentenceMatches && sentenceMatches.length > 0) {
    normalized = sentenceMatches.slice(0, 2).join(" ").trim();
  }

  if (!normalized) {
    return "Preview unavailable.";
  }

  if (normalized.length <= maxLength) {
    return normalized;
  }

  return `${normalized.slice(0, maxLength).trimEnd()}...`;
}

export function uniqueLatestDocuments(documents: DocumentRecord[]): DocumentRecord[] {
  const latestByFilename = new Map<string, DocumentRecord>();

  for (const document of documents) {
    const key = document.filename.trim().toLowerCase();
    const existing = latestByFilename.get(key);
    if (!existing || existing.id < document.id) {
      latestByFilename.set(key, document);
    }
  }

  return Array.from(latestByFilename.values()).sort((left, right) => right.id - left.id);
}

export function dedupeSources(sources: string[]): string[] {
  return Array.from(new Set(sources));
}

export function normalizeHistory(history: ChatHistoryRecord[]): ChatHistoryRecord[] {
  return history.map((item) => ({
    ...item,
    sources: dedupeSources(item.sources)
  }));
}
