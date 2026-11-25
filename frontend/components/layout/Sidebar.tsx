"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useActiveAlerts } from "@/features/alerts/hooks";
import { officialActiveCount } from "@/features/alerts/labels";
import { isActivePath, visibleNavItems, type NavItem } from "@/features/navigation/registry";

const MENU_ID = "menu-principal";

/** Número de alertas oficiais vigentes ao lado de "Alertas" (FR-147). */
export function AlertCountBadge({ count, active = false }: { count: number; active?: boolean }) {
  if (count === 0) return null;
  return (
    <span
      className={`ml-2 inline-flex min-w-5 justify-center rounded-full px-1.5 text-xs font-semibold ${
        active ? "bg-white text-accent" : "bg-status-error text-white"
      }`}
    >
      <span aria-hidden="true">{count}</span>
      {/* A vírgula separa o número do texto anterior em qualquer leitor de tela. */}
      <span className="sr-only">{`, ${count} ${count === 1 ? "alerta oficial vigente" : "alertas oficiais vigentes"}`}</span>
    </span>
  );
}

function NavList({ items, pathname, alerts }: { items: NavItem[]; pathname: string; alerts: number }) {
  return (
    <ul className="space-y-1">
      {items.map((item) => {
        const active = isActivePath(item.href, pathname);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`block rounded-md px-3 py-3 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent md:py-2 ${
                active ? "bg-accent text-white" : "text-ink hover:bg-surface-muted"
              }`}
            >
              {item.label}
              {item.href === "/alerts" && <AlertCountBadge count={alerts} active={active} />}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * Navegação principal. No computador, coluna fixa; abaixo de 768 px, barra com o botão "Menu"
 * e painel sobre o conteúdo, que fecha ao escolher uma página, com Esc e ao tocar fora (FR-200).
 */
export function SidebarView({ pathname, alerts }: { pathname: string; alerts: number }) {
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const nav = useRef<HTMLElement>(null);

  // Fecha ao trocar de página.
  useEffect(() => setOpen(false), [pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      button.current?.focus();
    };
    const onPointer = (event: PointerEvent) => {
      if (nav.current && !nav.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  return (
    <nav ref={nav} aria-label="Navegação principal" className="relative md:flex md:h-full md:flex-col md:gap-6 md:p-4">
      <div className="flex items-center justify-between gap-3 px-4 py-2 md:px-3 md:py-0">
        <div>
          <p className="text-base font-semibold text-ink">Inteligência Climática</p>
          <p className="text-xs text-ink-muted">São Paulo · piloto</p>
        </div>
        <button
          ref={button}
          type="button"
          aria-expanded={open}
          aria-controls={MENU_ID}
          onClick={() => setOpen((v) => !v)}
          className="inline-flex min-h-11 min-w-11 items-center rounded-md border border-surface-border px-3 text-sm font-medium text-ink hover:bg-surface-muted md:hidden"
        >
          Menu
          <AlertCountBadge count={alerts} />
        </button>
      </div>
      <div
        id={MENU_ID}
        className={`${
          open ? "block" : "hidden"
        } absolute inset-x-0 top-full z-40 max-h-[calc(100vh-4rem)] overflow-y-auto border-b border-surface-border bg-surface px-4 pb-4 shadow-lg md:static md:flex md:max-h-none md:flex-1 md:flex-col md:gap-6 md:overflow-visible md:border-0 md:p-0 md:shadow-none`}
      >
        <NavList items={visibleNavItems("primary")} pathname={pathname} alerts={alerts} />
        <div className="mt-4 border-t border-surface-border pt-4 md:mt-auto md:border-0 md:pt-0">
          <NavList items={visibleNavItems("secondary")} pathname={pathname} alerts={alerts} />
        </div>
      </div>
    </nav>
  );
}

export function Sidebar() {
  const pathname = usePathname() ?? "/";
  const { data } = useActiveAlerts();
  return <SidebarView pathname={pathname} alerts={officialActiveCount(data)} />;
}
