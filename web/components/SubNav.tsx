"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export interface SubNavItem {
  href: string;
  label: string;
}

export function SubNav({ items }: { items: SubNavItem[] }) {
  const pathname = usePathname();
  return (
    <div
      data-testid="subnav"
      className="px-4 py-2 flex gap-1.5 border-b"
      style={{
        background: "var(--color-surface)",
        borderColor: "var(--color-border)",
      }}
    >
      {items.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`subnav-tab ${active ? "subnav-tab-active" : "subnav-tab-inactive"}`}
          >
            {item.label}
          </Link>
        );
      })}
    </div>
  );
}
