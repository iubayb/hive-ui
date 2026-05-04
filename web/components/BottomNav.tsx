"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";

const NAV = [
  { href: "/hive",           label: "Status",  icon: "⬡" },
  { href: "/hive/assistant", label: "AI",      icon: "◈" },
  { href: "/hive/issues",    label: "Issues",  icon: "⊙" },
  { href: "/hive/commits",   label: "Commits", icon: "⊕" },
  { href: "/hive/explorer",  label: "Files",   icon: "⊞" },
];

const MORE = [
  { href: "/hive/pulls",     label: "Pulls",     icon: "⊃" },
  { href: "/hive/workflows", label: "Workflows", icon: "⊛" },
  { href: "/hive/analysis",  label: "Analysis",  icon: "⊘" },
  { href: "/hive/keys",      label: "Keys",      icon: "⊡" },
  { href: "/hive/logs",      label: "Logs",      icon: "⊟" },
];

export function BottomNav() {
  const path = usePathname();
  const [open, setOpen] = useState(false);

  // Close menu when navigating
  useEffect(() => { setOpen(false); }, [path]);

  const moreActive = MORE.some((item) => path.startsWith(item.href));

  return (
    <>
      {/* More popover overlay */}
      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />
          {/* Menu */}
          <div
            className="fixed bottom-[57px] right-0 z-50 w-44 rounded-tl-xl border overflow-hidden"
            style={{
              background: "rgba(9,9,11,0.97)",
              borderColor: "var(--color-border)",
              backdropFilter: "blur(20px)",
            }}
          >
            {MORE.map((item) => {
              const active = path.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="flex items-center gap-3 px-4 py-3 transition-colors border-b last:border-0"
                  style={{
                    borderColor: "var(--color-border)",
                    color: active ? "var(--color-brand)" : "var(--color-text-secondary)",
                    background: active ? "rgba(255,255,255,0.03)" : "transparent",
                  }}
                >
                  <span className="text-base leading-none">{item.icon}</span>
                  <span className="text-sm font-medium">{item.label}</span>
                </Link>
              );
            })}
          </div>
        </>
      )}

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
          {/* More button */}
          <li className="flex-1">
            <button
              onClick={() => setOpen((v) => !v)}
              className="flex flex-col items-center justify-center gap-0.5 w-full transition-colors"
              style={{
                minHeight: "56px",
                color: open || moreActive
                  ? "var(--color-brand)"
                  : "var(--color-text-muted)",
              }}
            >
              <span className="text-lg leading-none">⋯</span>
              <span className="text-[10px] font-medium">More</span>
            </button>
          </li>
        </ul>
      </nav>
    </>
  );
}
