"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { isActivePath, visibleNavItems, type NavItem } from "@/features/navigation/registry";

function NavList({ items, pathname }: { items: NavItem[]; pathname: string }) {
  return (
    <ul className="space-y-1">
      {items.map((item) => {
        const active = isActivePath(item.href, pathname);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`block rounded-md px-3 py-2 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                active ? "bg-accent text-white" : "text-ink hover:bg-surface-muted"
              }`}
            >
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export function Sidebar() {
  const pathname = usePathname() ?? "/";
  return (
    <nav aria-label="Navegação principal" className="flex h-full flex-col gap-6 p-4">
      <div className="px-3">
        <p className="text-base font-semibold text-ink">Inteligência Climática</p>
        <p className="text-xs text-ink-muted">São Paulo · piloto</p>
      </div>
      <NavList items={visibleNavItems("primary")} pathname={pathname} />
      <div className="mt-auto">
        <NavList items={visibleNavItems("secondary")} pathname={pathname} />
      </div>
    </nav>
  );
}
