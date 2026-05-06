import { ghFetch } from "@/lib/github";
import { PageHeader } from "@/components/PageHeader";
import { SubNav } from "@/components/SubNav";

export const revalidate = 120;

const WORKFLOWS_COMMITS_NAV = [
  { href: "/hive/workflows", label: "Workflows" },
  { href: "/hive/commits",   label: "Commits"   },
];

export default async function CommitsPage() {
  let commits: any[] = [];
  try {
    commits = await ghFetch<any[]>("/commits?per_page=30", { revalidate: 120 });
  } catch {}

  return (
    <div style={{ background: "var(--color-surface)" }}>
      <PageHeader icon="⊕" title="Commits" />
      <SubNav items={WORKFLOWS_COMMITS_NAV} />

      <main className="px-4 py-4 space-y-2 max-w-lg mx-auto">
        {commits.length === 0 ? (
          <div className="glass-card p-8 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>
            No commits found
          </div>
        ) : (
          commits.map((c) => (
            <a
              key={c.sha}
              href={c.html_url}
              target="_blank"
              rel="noreferrer"
              className="glass-card-hover block p-3 space-y-1"
            >
              <p className="text-sm" style={{ color: "var(--color-text-primary)" }}>
                {c.commit?.message?.split("\n")[0].slice(0, 80)}
              </p>
              <div className="flex gap-2 items-center">
                <span className="text-xs font-mono" style={{ color: "var(--color-brand)" }}>
                  {c.sha?.slice(0, 7)}
                </span>
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {c.commit?.author?.name} · {new Date(c.commit?.author?.date).toLocaleDateString()}
                </span>
              </div>
            </a>
          ))
        )}
      </main>
    </div>
  );
}
