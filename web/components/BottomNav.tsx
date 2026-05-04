"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/hive",            label: "Status",  icon: "⬡" },
  { href: "/hive/assistant",  label: "AI",      icon: "◈" },
  { href: "/hive/issues",     label: "Issues",  icon: "⊙" },
  { href: "/hive/commits",    label: "Commits", icon: "⊕" },
  { href: "/hive/explorer",   label: "Files",   icon: "⊞" },
];

export function BottomNav() {
  const path = usePathname();
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 border-t"
      style={{
        background: "rgba(9,9,11,0.96)",
        borderColor: "var(--color-border)",
        backdropFilter: "blur(16px)",
      }}
    >
      <ul className="flex items-stretch justify-around max-w-lg mx-auto">
        {NAV.map((item) => {
          const active =
            path === item.href ||
            (item.href !== "/hive" && path.startsWith(item.href));
          return (
            <li key={item.href} className="flex-1">
              <Link
                href={item.href}
                className="flex flex-col items-center justify-center gap-0.5 w-full transition-colors"
                style={{
                  minHeight: "56px",
                  color: active
                    ? "var(--color-brand)"
                    : "var(--color-text-muted)",
                }}
              >
                <span className="text-lg leading-none">{item.icon}</span>
                <span className="text-[10px] font-medium">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
