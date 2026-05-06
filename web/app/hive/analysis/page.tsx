export const revalidate = 3600;

async function getReport() {
  try {
    const res = await fetch(
      "https://raw.githubusercontent.com/iubayb/hive-ui/status/research/latest.md",
      { next: { revalidate: 3600 } }
    );
    if (!res.ok) return null;
    return res.text();
  } catch {
    return null;
  }
}

/** Minimal inline Markdown → JSX renderer (no external deps). */
function renderMarkdown(md: string) {
  const esc = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const inline = (s: string) =>
    esc(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`(.+?)`/g, '<code class="bg-white/5 px-1 rounded text-xs font-mono">$1</code>')
      .replace(
        /\[(.+?)\]\((https?:\/\/[^\)]+)\)/g,
        '<a href="$2" target="_blank" rel="noreferrer" class="underline" style="color:var(--color-brand)">$1</a>'
      );

  const lines = md.split("\n");
  const out: string[] = [];
  let inList = false;

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const trimmed = raw.trimEnd();

    if (/^### /.test(trimmed)) {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<h3 class="text-xs font-semibold uppercase tracking-wider mt-4 mb-1" style="color:var(--color-text-muted)">${inline(trimmed.slice(4))}</h3>`);
    } else if (/^## /.test(trimmed)) {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<h2 class="text-sm font-semibold mt-5 mb-1.5" style="color:var(--color-text-primary)">${inline(trimmed.slice(3))}</h2>`);
    } else if (/^# /.test(trimmed)) {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<h1 class="text-base font-bold mt-4 mb-2" style="color:var(--color-text-primary)">${inline(trimmed.slice(2))}</h1>`);
    } else if (/^[-*] /.test(trimmed)) {
      if (!inList) { out.push('<ul class="list-disc list-inside space-y-0.5 text-xs my-1.5" style="color:var(--color-text-secondary)">'); inList = true; }
      out.push(`<li>${inline(trimmed.slice(2))}</li>`);
    } else if (/^\d+\. /.test(trimmed)) {
      if (!inList) { out.push('<ol class="list-decimal list-inside space-y-0.5 text-xs my-1.5" style="color:var(--color-text-secondary)">'); inList = true; }
      out.push(`<li>${inline(trimmed.replace(/^\d+\. /, ""))}</li>`);
    } else if (trimmed === "" || trimmed === "---") {
      if (inList) { out.push("</ul>"); inList = false; }
      if (trimmed === "---") out.push('<hr class="border-white/10 my-3" />');
      else out.push('<div class="h-1.5"></div>');
    } else {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<p class="text-xs leading-relaxed" style="color:var(--color-text-secondary)">${inline(trimmed)}</p>`);
    }
  }
  if (inList) out.push("</ul>");
  return out.join("\n");
}

import { PageHeader } from "@/components/PageHeader";

export default async function AnalysisPage() {
  const report = await getReport();

  return (
    <div style={{ background: "var(--color-surface)" }}>
      <PageHeader icon="⊘" title="Audit" subtitle="research/latest.md" />
      <main className="px-4 py-4 max-w-lg mx-auto">
        {report ? (
          <div
            className="glass-card p-4 overflow-y-auto"
            style={{ maxHeight: "calc(100dvh - 170px)" }}
          >
            <div dangerouslySetInnerHTML={{ __html: renderMarkdown(report) }} />
          </div>
        ) : (
          <div className="glass-card p-8 text-center space-y-2">
            <p className="text-2xl" style={{ color: "var(--color-text-muted)" }}>⊘</p>
            <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              No analysis report yet
            </p>
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Push research/latest.md to the status/ branch
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
