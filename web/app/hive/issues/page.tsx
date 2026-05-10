import { ghFetch } from "@/lib/github";
import { PageHeader } from "@/components/PageHeader";
import { SubNav } from "@/components/SubNav";

export const revalidate = 60;

const ISSUES_PULLS_NAV = [
  { href: "/hive/issues", label: "Issues" },
  { href: "/hive/pulls",  label: "PRs"    },
];

export default async function IssuesPage() {
  let issues: any[] = [];
  try {
    issues = await ghFetch<any[]>("/issues?state=open&per_page=30", { revalidate: 60 });
  } catch {}

  return (
    <div style={{ background: "var(--color-surface)" }}>
      <PageHeader
        icon="⊙"
        title="Issues"
        subtitle={`${issues.length} open`}
      />
      <SubNav items={ISSUES_PULLS_NAV} />

      <main className="px-4 py-4 space-y-2 max-w-lg mx-auto">
        {issues.length === 0 ? (
          <div className="glass-card p-8 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>
            No open issues
          </div>
        ) : (
          issues.map((issue) => (
            <a
              key={issue.id}
              href={issue.html_url}
              target="_blank"
              rel="noreferrer"
              className="glass-card-hover block p-4 space-y-1.5"
            >
              <div className="flex items-start gap-2">
                <span className="text-xs font-mono shrink-0 mt-0.5" style={{ color: "var(--color-text-muted)" }}>
                  #{issue.number}
                </span>
                <p className="text-sm flex-1" style={{ color: "var(--color-text-primary)" }}>
                  {issue.title}
                </p>
              </div>
              <div className="flex gap-1 flex-wrap pl-5">
                {issue.labels?.map((l: any) => (
                  <span
                    key={l.id}
                    className="text-[10px] px-1.5 py-0.5 rounded-full"
                    style={{
                      background: `#${l.color}22`,
                      color: `#${l.color}`,
                      border: `1px solid #${l.color}44`,
                    }}
                  >
                    {l.name}
                  </span>
                ))}
              </div>
            </a>
          ))
        )}
      </main>
    </div>
  );
}
