import { ghFetch } from "@/lib/github";
import { PageHeader } from "@/components/PageHeader";

export const revalidate = 120;

export default async function ExplorerPage() {
  let contents: any[] = [];
  try {
    contents = await ghFetch<any[]>("/contents", { revalidate: 120 });
  } catch {}

  return (
    <div style={{ background: "var(--color-surface)" }}>
      <PageHeader icon="⊞" title="Explorer" subtitle="repo root" />
      <main className="px-4 py-4 space-y-1 max-w-lg mx-auto">
        {contents.length === 0 ? (
          <div className="glass-card p-8 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>
            No files found
          </div>
        ) : (
          contents
            .sort((a, b) => (a.type === "dir" ? -1 : 1))
            .map((item) => (
              <a
                key={item.sha}
                href={item.html_url}
                target="_blank"
                rel="noreferrer"
                className="glass-card-hover flex items-center gap-2 px-3 py-2"
              >
                {/* Geometric type indicator */}
                <span
                  className="text-xs font-mono shrink-0"
                  style={{
                    color: item.type === "dir"
                      ? "var(--color-brand)"
                      : "var(--color-text-muted)",
                  }}
                >
                  {item.type === "dir" ? "▸" : "◻"}
                </span>
                <span
                  className="text-sm font-mono flex-1"
                  style={{
                    color: item.type === "dir"
                      ? "var(--color-brand)"
                      : "var(--color-text-secondary)",
                  }}
                >
                  {item.name}
                </span>
                {item.type === "file" && (
                  <span className="text-xs font-mono shrink-0" style={{ color: "var(--color-text-muted)" }}>
                    {item.size > 1024
                      ? `${(item.size / 1024).toFixed(1)}k`
                      : `${item.size}b`}
                  </span>
                )}
              </a>
            ))
        )}
      </main>
    </div>
  );
}
