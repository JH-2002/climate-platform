import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";
import { BasinCard } from "@/components/geo/BasinCard";
import { BasinRanking } from "@/components/geo/BasinRanking";
import { ProfileChart } from "@/components/geo/ProfileChart";
import { TerrainSection, relativeLabel } from "@/components/geo/TerrainSection";
import { profileQuery } from "@/features/geo/api";
import { PROFILE_EXAMPLES, parseGeoState, serializeGeoState } from "@/features/geo/state";
import { basinDetail, basinList, profileFixture, terrainFixture } from "./geoFixtures";
import { renderWithQuery } from "./query";

async function seriousViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { region: { enabled: false } } });
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

describe("estado da página /geo-3d", () => {
  it("ida e volta pela URL", () => {
    const state = { tab: "perfil" as const, basinId: 252, sort: "ocorrencias" as const, profile: PROFILE_EXAMPLES[0]!.points };
    expect(parseGeoState(new URLSearchParams(serializeGeoState(state)))).toEqual(state);
  });

  it("valores inválidos voltam ao padrão", () => {
    const parsed = parseGeoState(new URLSearchParams("aba=x&bacia=-3&ordem=y&perfil=abc;1,2,3"));
    expect(parsed).toEqual({ tab: "bacias", basinId: null, sort: "alto", profile: [] });
  });

  it("perfil vai para a API com 5 casas", () => {
    expect(profileQuery([[-46.551234, -23.5], [-46.5, -23.49]])).toBe("-46.55123,-23.50000;-46.50000,-23.49000");
  });
});

describe("TerrainSection (FR-127)", () => {
  it("descreve o relevo em palavras e cita fonte e aviso", async () => {
    const { container } = renderWithQuery(<TerrainSection sectorId={4} />, [[["geo", "sector", 4], terrainFixture(4)]]);
    expect(screen.getByRole("heading", { name: "Terreno" })).toBeInTheDocument();
    expect(screen.getByText("12 m abaixo do entorno (fundo de vale)")).toBeInTheDocument();
    expect(screen.getByText(/Ribeirão Água Vermelha a 84 m — trecho em estado natural/)).toBeInTheDocument();
    expect(screen.getByText(/modelo de superfície/)).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("avisa quando o setor tem pouca amostra", () => {
    renderWithQuery(<TerrainSection sectorId={5} />, [[["geo", "sector", 5], terrainFixture(5, { cells: 2, low_sample: true })]]);
    expect(screen.getByText(/só 2 célula\(s\)/)).toBeInTheDocument();
  });

  it("rótulos do relevo relativo", () => {
    expect(relativeLabel(null)).toBe("sem dado");
    expect(relativeLabel(2)).toBe("no nível do entorno");
    expect(relativeLabel(18.4)).toBe("18 m acima do entorno (parte alta)");
  });
});

describe("bacias", () => {
  it("ranking ordena, seleciona e conta setores fora das bacias", async () => {
    const onSort = vi.fn();
    const onSelect = vi.fn();
    const { container } = render(
      <BasinRanking list={basinList} sort="alto" selectedId={null} onSort={onSort} onSelect={onSelect} />,
    );
    expect(screen.getByText(/44 setores de risco em 2 bacias; 1 fora das bacias mapeadas/)).toBeInTheDocument();
    const row = screen.getByRole("rowheader", { name: /Rio Aricanduva/ }).closest("tr")!;
    expect(within(row).getByText("1.250 mil m³")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ver a ficha da bacia Rio Aricanduva" }));
    expect(onSelect).toHaveBeenCalledWith(252);
    fireEvent.change(screen.getByLabelText("Ordenar por"), { target: { value: "piscinoes" } });
    expect(onSort).toHaveBeenCalledWith("piscinoes");
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("ficha mostra números, setores com relevo e piscinões", async () => {
    const { container } = render(<BasinCard detail={basinDetail} onClose={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Rio Aricanduva" })).toBeInTheDocument();
    expect(screen.getByText("722–890 m")).toBeInTheDocument();
    expect(screen.getByText("58,2 / 31,5 km")).toBeInTheDocument();
    expect(screen.getByText("14 m abaixo do entorno (fundo de vale)")).toBeInTheDocument();
    expect(screen.getByText("Aricanduva V")).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("perfil (FR-124)", () => {
  it("resume o perfil e lista o que cruza, em tabela", async () => {
    const { container } = render(<ProfileChart profile={profileFixture} />);
    expect(screen.getByText(/elevação de 724 a 740 m/)).toBeInTheDocument();
    expect(screen.getByText(/Cruza 1 curso\(s\) d’água e 1 setor\(es\) de risco/)).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "O que o perfil cruza" });
    expect(within(table).getByRole("rowheader", { name: "Curso d’água: Rio Tietê" })).toBeInTheDocument();
    expect(within(table).getByRole("rowheader", { name: "Setor de risco HMP-01-03" })).toBeInTheDocument();
    expect(screen.getByText("Calculado")).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });
});
