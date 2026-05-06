"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/hive",            label: "Hive",   icon: "⬡" },
  { href: "/hive/issues",     label: "Issues", icon: "⊙" },
  { href: "/hive/assistant",  label: "AI",     icon: "◈" },
  { href: "/hive/analysis",   label: "Audit",  icon: "⊘" },
  { href: "/hive/workflows",  label: "CI",     icon: "⊛" },
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
        paddingBottom: "env(safe-area-inset-bottom)",
      }}
    >
      <ul className="flex items-stretch justify-around w-full max-w-lg mx-auto overflow-hidden">
        {NAV.map((item) => {
          const active =
            path === item.href ||
            (item.href !== "/hive" && path.startsWith(item.href));
          return (
            <li key={item.href} className="flex-1 min-w-0">
              <Link
                href={item.href}
                className="flex flex-col items-center justify-center gap-0.5 w-full transition-colors"
                style={{
                  minHeight: "44px",
                  color: active ? "#00DC82" : "var(--color-text-muted)",
                }}
              >
                <span className="text-lg leading-none">{item.icon}</span>
                <span className="text-[10px] font-medium truncate">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
