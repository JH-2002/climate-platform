import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OFFLINE_MESSAGE, OfflineBannerView } from "@/components/layout/OfflineBanner";
import { serviceWorkerUrl } from "@/components/layout/PwaRegister";
import { SidebarView } from "@/components/layout/Sidebar";

describe("menu recolhível (FR-200, AC-201)", () => {
  it("abre pelo botão, fecha com Esc e devolve o foco", () => {
    render(<SidebarView pathname="/" alerts={2} />);
    const button = screen.getByRole("button", { name: /^Menu/ });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveAttribute("aria-controls", "menu-principal");
    expect(document.getElementById("menu-principal")).toHaveClass("hidden");

    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(document.getElementById("menu-principal")).toHaveClass("block");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveFocus();
  });

  it("fecha ao tocar fora", () => {
    render(
      <div>
        <SidebarView pathname="/" alerts={0} />
        <p>conteúdo</p>
      </div>,
    );
    const button = screen.getByRole("button", { name: "Menu" });
    fireEvent.click(button);
    fireEvent.pointerDown(screen.getByText("conteúdo"));
    expect(button).toHaveAttribute("aria-expanded", "false");
  });

  it("fecha ao trocar de página", () => {
    const { rerender } = render(<SidebarView pathname="/" alerts={0} />);
    fireEvent.click(screen.getByRole("button", { name: "Menu" }));
    rerender(<SidebarView pathname="/risk" alerts={0} />);
    expect(screen.getByRole("button", { name: "Menu" })).toHaveAttribute("aria-expanded", "false");
  });

  it("o botão mostra os alertas oficiais vigentes", () => {
    render(<SidebarView pathname="/" alerts={3} />);
    expect(screen.getByRole("button", { name: "Menu, 3 alertas oficiais vigentes" })).toBeInTheDocument();
  });

  it("a página atual fica marcada", () => {
    render(<SidebarView pathname="/risk" alerts={0} />);
    expect(screen.getByRole("link", { name: "Risco de alagamento" })).toHaveAttribute("aria-current", "page");
  });
});

describe("sem conexão (FR-204, BR-200)", () => {
  it("mostra o aviso só sem conexão", () => {
    const { rerender } = render(<OfflineBannerView online />);
    expect(screen.queryByText(OFFLINE_MESSAGE)).toBeNull();
    rerender(<OfflineBannerView online={false} />);
    expect(screen.getByText(OFFLINE_MESSAGE)).toBeInTheDocument();
  });
});

describe("registro do service worker (FR-203)", () => {
  it("na raiz e com o prefixo da vitrine", () => {
    expect(serviceWorkerUrl("")).toEqual({ url: "/sw.js?base=", scope: "/" });
    expect(serviceWorkerUrl("/climate-platform")).toEqual({
      url: "/climate-platform/sw.js?base=%2Fclimate-platform",
      scope: "/climate-platform/",
    });
  });
});
