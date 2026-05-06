import { ghFetch } from "@/lib/github";

export const revalidate = 60;

export default async function PullsPage() {
  let pulls: any[] = [];
  try {
    pulls = await ghFetch<any[]>("/pulls?state=open&per_page=30", { revalidate: 60 });
  } catch {}

  return (
    <div style={{ background: "var(--color-surface)" }}>
      <header
        className="sticky top-0 z-40 px-4 py-3 flex items-center gap-2 border-b"
        style={{
          background: "rgba(9,9,11,0.95)",
          borderColor: "var(--color-border)",
          backdropFilter: "blur(16px)",
        }}
      >
        <span className="text-lg">⊗</span>
        <span className="font-display font-semibold text-sm">Pull Requests</span>
        <span className="ml-auto text-xs font-mono" style={{ color: "var(--color-text-muted)" }}>
          {pulls.length} open
        </span>
      </header>
      <main className="px-4 py-4 space-y-2 max-w-lg mx-auto">
        {pulls.length === 0 ? (
          <div className="glass-card p-8 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>
            No open pull requests
          </div>
        ) : (
          pulls.map((pr) => (
            <a
              key={pr.id}
              href={pr.html_url}
              target="_blank"
              rel="noreferrer"
              className="glass-card-hover block p-4 space-y-1"
            >
              <div className="flex items-start gap-2">
                <span className="text-xs font-mono shrink-0 mt-0.5" style={{ color: "var(--color-text-muted)" }}>
                  #{pr.number}
                </span>
                <div className="flex-1">
                  <p className="text-sm" style={{ color: "var(--color-text-primary)" }}>{pr.title}</p>
                  <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>
                    {pr.head?.ref} → {pr.base?.ref}
                  </p>
                </div>
              </div>
            </a>
          ))
        )}
      </main>
    </div>
  );
}
