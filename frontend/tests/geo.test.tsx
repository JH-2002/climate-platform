import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";
import { BasinBlock2D, categorySummary } from "@/components/geo/BasinBlock2D";
import { BasinBlockView } from "@/components/geo/BasinBlockView";
import { BasinCard } from "@/components/geo/BasinCard";
import { BasinRanking } from "@/components/geo/BasinRanking";
import { ProfileChart } from "@/components/geo/ProfileChart";
import { TerrainSection, relativeLabel } from "@/components/geo/TerrainSection";
import { profileQuery } from "@/features/geo/api";
import { PROFILE_EXAMPLES, parseGeoState, serializeGeoState } from "@/features/geo/state";
import { basinDetail, basinList, blockFixture, profileFixture, terrainFixture } from "./geoFixtures";
import { renderWithQuery } from "./query";

async function seriousViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { region: { enabled: false } } });
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

describe("estado da página /geo-3d", () => {
  it("ida e volta pela URL", () => {
    const state = {
      tab: "bloco" as const,
      basinId: 252,
      sort: "ocorrencias" as const,
      profile: PROFILE_EXAMPLES[0]!.points,
      simulationId: "4f9c2a8e-1b2d-4c3e-9f00-123456789abc",
    };
    expect(parseGeoState(new URLSearchParams(serializeGeoState(state)))).toEqual(state);
  });

  it("valores inválidos voltam ao padrão", () => {
    const parsed = parseGeoState(new URLSearchParams("aba=x&bacia=-3&ordem=y&perfil=abc;1,2,3&simulacao=zzz"));
    expect(parsed).toEqual({ tab: "bacias", basinId: null, sort: "alto", profile: [], simulationId: null });
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

describe("bloco da bacia (Parte B)", () => {
  it("resume as categorias em texto", () => {
    expect(categorySummary(blockFixture)).toBe("1 crítico, 1 alto, 1 baixo");
    expect(categorySummary({ ...blockFixture, sectors: [] })).toBe("nenhum setor de risco");
  });

  it("versão 2D: imagem com texto alternativo e tabela com a chance da simulação", async () => {
    const { container } = render(<BasinBlock2D block={blockFixture} />);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", `/api/v1/geo/basins/9/relief.png?simulacao=${blockFixture.simulation_id}`);
    expect(img.getAttribute("alt")).toMatch(/Setores de risco \(3\): 1 crítico, 1 alto, 1 baixo/);
    expect(screen.getByRole("columnheader", { name: "Chance de alto ou crítico" })).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("sem bacia escolhida, pede para escolher uma", () => {
    renderWithQuery(<BasinBlockView basinId={null} simulationId={null} onSimulation={vi.fn()} />, [
      [["simulation", "recent"], []],
    ]);
    expect(screen.getByText(/Escolha uma bacia no mapa ou no ranking/)).toBeInTheDocument();
  });

  it("sem WebGL mostra a versão 2D, com a faixa de simulação (AC-124, AC-125)", () => {
    const onSimulation = vi.fn();
    renderWithQuery(
      <BasinBlockView basinId={9} simulationId={blockFixture.simulation_id} onSimulation={onSimulation} />,
      [
        [["geo", "block", 9, blockFixture.simulation_id], blockFixture],
        [["simulation", "recent"], []],
      ],
    );
    expect(screen.getByText(/não tem WebGL: mostrando a versão em 2D/)).toBeInTheDocument();
    expect(screen.getByRole("note", { name: "Aviso de simulação" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "3D" })).toBeDisabled();
    expect(screen.getByRole("img")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Cores dos setores"), { target: { value: "" } });
    expect(onSimulation).toHaveBeenCalledWith(null);
  });
});
