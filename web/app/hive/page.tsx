import { HiveDashboard } from "./HiveDashboard";
import { PageHeader } from "@/components/PageHeader";
import Link from "next/link";

export const revalidate = 30;

async function getStatus() {
  try {
    const res = await fetch(
      "https://raw.githubusercontent.com/iubayb/hive-ui/status/hive-status.json",
      { next: { revalidate: 30 } }
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

const QUICK_LINKS = [
  { href: "/hive/logs",      label: "Logs"      },
  { href: "/hive/keys",      label: "Keys"      },
  { href: "/hive/explorer",  label: "Files"     },
  { href: "/hive/knowledge", label: "Knowledge" },
  { href: "/hive/tracker",   label: "Tracker"   },
  { href: "/hive/settings",  label: "Settings"  },
];

export default async function HivePage() {
  const status = await getStatus();
  const lastUpdated = status?.last_updated
    ? `updated ${String(status.last_updated).slice(11, 16)} UTC`
    : undefined;

  return (
    <div style={{ background: "var(--color-surface)" }}>
      <PageHeader icon="⬡" title="HIVE" subtitle={lastUpdated} />

      {/* Quick-links chip strip */}
      <div
        className="px-4 py-2 flex gap-1.5 overflow-x-auto border-b"
        style={{
          background: "var(--color-surface)",
          borderColor: "var(--color-border)",
          scrollbarWidth: "none",
        }}
      >
        {QUICK_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="shrink-0 px-3 rounded-full text-[11px] font-medium transition-colors"
            style={{
              background: "var(--color-glass)",
              color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
              lineHeight: "28px",
              display: "inline-block",
              whiteSpace: "nowrap",
            }}
          >
            {link.label}
          </Link>
        ))}
      </div>

      <main className="px-4 py-4 max-w-lg mx-auto">
        <HiveDashboard initialStatus={status} />
      </main>
    </div>
  );
}
