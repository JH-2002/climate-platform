/**
 * Fonte única da navegação (FR-010).
 * Um módulo só aparece na interface quando `implemented` é true — sem links mortos.
 * Mude a flag no mesmo PR que entrega o módulo.
 */

export type NavSection = "primary" | "secondary";

export interface NavItem {
  href: string;
  label: string;
  section: NavSection;
  phase: number;
  implemented: boolean;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/", label: "Visão geral", section: "primary", phase: 1, implemented: true },
  { href: "/alerts", label: "Alertas", section: "primary", phase: 9, implemented: true },
  { href: "/weather", label: "Clima", section: "primary", phase: 3, implemented: true },
  { href: "/map", label: "Mapa", section: "primary", phase: 4, implemented: true },
  { href: "/risk", label: "Risco de alagamento", section: "primary", phase: 5, implemented: true },
  { href: "/analytics", label: "Análises", section: "primary", phase: 6, implemented: true },
  {
    href: "/simulation",
    label: "Laboratório de simulação",
    section: "primary",
    phase: 7,
    implemented: true,
  },
  { href: "/geo-3d", label: "Geointeligência 3D", section: "primary", phase: 8, implemented: true },
  { href: "/reports", label: "Relatórios", section: "primary", phase: 10, implemented: true },
  { href: "/locations", label: "Meus locais", section: "secondary", phase: 3, implemented: false },
  {
    href: "/analytics/datasets",
    label: "Explorador de dados",
    section: "secondary",
    phase: 6,
    implemented: true,
  },
  { href: "/status", label: "Estado do sistema", section: "secondary", phase: 1, implemented: true },
];

export function visibleNavItems(
  section: NavSection,
  items: readonly NavItem[] = NAV_ITEMS,
): NavItem[] {
  return items.filter((item) => item.implemented && item.section === section);
}

export function isActivePath(itemHref: string, pathname: string): boolean {
  if (itemHref === "/") return pathname === "/";
  return pathname === itemHref || pathname.startsWith(`${itemHref}/`);
}
