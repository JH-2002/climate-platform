import { describe, expect, it } from "vitest";
import { NAV_ITEMS, isActivePath, visibleNavItems, type NavItem } from "@/features/navigation/registry";

describe("registro de navegação (FR-010)", () => {
  it("mostra apenas módulos implementados", () => {
    const primary = visibleNavItems("primary");
    const secondary = visibleNavItems("secondary");
    expect(primary.map((i) => i.href)).toEqual(["/", "/weather", "/map", "/risk", "/analytics", "/simulation"]);
    expect(secondary.map((i) => i.href)).toEqual(["/analytics/datasets", "/status"]);
  });

  it("esconde módulo não implementado mesmo que esteja registrado", () => {
    const items: NavItem[] = [
      { href: "/a", label: "A", section: "primary", phase: 1, implemented: true },
      { href: "/b", label: "B", section: "primary", phase: 9, implemented: false },
    ];
    expect(visibleNavItems("primary", items).map((i) => i.href)).toEqual(["/a"]);
  });

  it("não tem hrefs repetidos", () => {
    const hrefs = NAV_ITEMS.map((i) => i.href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });

  it("identifica a rota ativa sem tratar '/' como prefixo de tudo", () => {
    expect(isActivePath("/", "/")).toBe(true);
    expect(isActivePath("/", "/status")).toBe(false);
    expect(isActivePath("/status", "/status")).toBe(true);
    expect(isActivePath("/status", "/status/detalhes")).toBe(true);
    expect(isActivePath("/stat", "/status")).toBe(false);
  });
});
