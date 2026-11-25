import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DemoBannerView } from "@/components/layout/DemoBanner";
import { apiGet, apiPost, ApiError } from "@/lib/api-client";
import {
  DEMO_MESSAGES,
  assetUrl,
  canonicalJson,
  canonicalQuery,
  demoFallbackFile,
  demoFile,
  demoUrl,
  fnv1a,
} from "@/lib/demo";

describe("chaves dos arquivos da demonstração (AC-194)", () => {
  it("FNV-1a de 32 bits com valores conhecidos", () => {
    expect(fnv1a("")).toBe("811c9dc5");
    expect(fnv1a("a")).toBe("e40c292c");
    expect(fnv1a("foobar")).toBe("bf9cf968");
  });

  it("consulta canônica ignora a ordem e normaliza a codificação", () => {
    expect(canonicalQuery("?b=2&a=1")).toBe("a=1&b=2");
    expect(canonicalQuery("a=1&b=2")).toBe(canonicalQuery("b=2&a=1"));
    expect(canonicalQuery("nome=S%C3%A3o+Paulo")).toBe("nome=S%C3%A3o%20Paulo");
    expect(canonicalQuery("x=2&x=1")).toBe("x=1&x=2");
    expect(canonicalQuery("")).toBe("");
  });

  it("JSON canônico ordena as chaves em qualquer nível", () => {
    expect(canonicalJson({ b: 1, a: { d: [2, { y: 1, x: 0 }], c: null } })).toBe(
      '{"a":{"c":null,"d":[2,{"x":0,"y":1}]},"b":1}',
    );
    expect(canonicalJson({ a: undefined, b: 1 })).toBe('{"b":1}');
  });

  it("caminhos com e sem consulta, com extensão e POST", () => {
    expect(demoFile("GET", "/api/v1/risk/summary")).toBe("risk/summary/index.json");
    expect(demoFile("GET", "/api/v1/risk/areas?b=2&a=1")).toBe(`risk/areas/q-${fnv1a("a=1&b=2")}.json`);
    expect(demoFile("GET", "/api/v1/risk/areas?a=1&b=2")).toBe(demoFile("GET", "/api/v1/risk/areas?b=2&a=1"));
    expect(demoFile("GET", "/api/v1/geo/basins/3/relief.png")).toBe("geo/basins/3/relief.png");
    expect(demoFile("GET", "/api/v1/geo/basins/3/relief.png?simulacao=x")).toBe(
      `geo/basins/3/relief.q-${fnv1a("simulacao=x")}.png`,
    );
    expect(demoFile("GET", "http://localhost:3000/api/v1/alerts/active")).toBe("alerts/active/index.json");
    expect(demoFile("POST", "/api/v1/simulation/runs", { b: 1, a: 2 })).toBe(
      `simulation/runs/post-${fnv1a('{"a":2,"b":1}')}.json`,
    );
  });

  it("fora da API ou com caminho suspeito não há arquivo", () => {
    expect(demoFile("GET", "/outra/coisa")).toBeNull();
    expect(demoFile("GET", "/api/v1/../segredo")).toBeNull();
    expect(demoFile("GET", "/api/v1/")).toBeNull();
  });

  it("reserva sem consulta só existe quando havia consulta", () => {
    expect(demoFallbackFile("/api/v1/risk/areas?categoria=HIGH")).toBe("risk/areas/index.json");
    expect(demoFallbackFile("/api/v1/risk/areas")).toBeNull();
  });
});

describe("cliente da API no modo demonstração (FR-190, FR-191)", () => {
  const files = new Map<string, unknown>();
  const fetchImpl = vi.fn(async (url: string | URL | Request) => {
    const key = String(url);
    return files.has(key)
      ? new Response(JSON.stringify(files.get(key)), { status: 200 })
      : new Response("não encontrado", { status: 404 });
  }) as unknown as typeof fetch;

  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_DEMO", "1");
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/climate-platform");
    files.clear();
  });
  afterEach(() => vi.unstubAllEnvs());

  it("lê a resposta gravada no caminho do site", async () => {
    files.set("/climate-platform/demo-data/risk/summary/index.json", { total: 793 });
    const { data } = await apiGet<{ total: number }>("/api/v1/risk/summary", { fetchImpl });
    expect(data.total).toBe(793);
  });

  it("sem a consulta exata usa a resposta do caminho sem consulta", async () => {
    files.set(demoUrl("risk/areas/index.json"), { items: [] });
    const { data } = await apiGet("/api/v1/risk/areas?categoria=HIGH", { fetchImpl });
    expect(data).toEqual({ items: [] });
  });

  it("sem nenhuma gravação explica que é a demonstração", async () => {
    await expect(apiGet("/api/v1/geo/profile?pontos=1,2", { fetchImpl })).rejects.toMatchObject({
      message: DEMO_MESSAGES.unavailable,
      status: 404,
    });
  });

  it("simulação de cenário pronto devolve a gravada; outra explica o limite", async () => {
    const body = { mode: "SIMULATION", rain_mm: 50 };
    files.set(demoUrl(demoFile("POST", "/api/v1/simulation/runs", body)!), { id: "abc" });
    const { data } = await apiPost<{ id: string }>("/api/v1/simulation/runs", { rain_mm: 50, mode: "SIMULATION" }, { fetchImpl });
    expect(data.id).toBe("abc");
    const error = await apiPost("/api/v1/simulation/runs", { rain_mm: 51 }, { fetchImpl }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe(DEMO_MESSAGES.simulation);
  });

  it("relatórios ficam desligados", async () => {
    await expect(apiPost("/api/v1/reports", { type: "situacao" }, { fetchImpl })).rejects.toMatchObject({
      message: DEMO_MESSAGES.reports,
    });
  });

  it("URLs diretas (imagem, blocos) apontam para os arquivos gravados", () => {
    expect(assetUrl("/api/v1/geo/terrain/{z}/{x}/{y}.png")).toBe("/climate-platform/demo-data/geo/terrain/{z}/{x}/{y}.png");
  });
});

describe("fora do modo demonstração nada muda", () => {
  it("URLs diretas continuam na API", () => {
    expect(assetUrl("/api/v1/geo/basins/3/relief.png")).toBe("/api/v1/geo/basins/3/relief.png");
  });
});

describe("faixa da demonstração (FR-192, BR-190)", () => {
  it("mostra que é demonstração, de quando são os dados e o link do código", () => {
    render(<DemoBannerView meta={{ recorded_at: "2026-11-25T18:00:00Z" }} />);
    expect(screen.getByText("Demonstração pública")).toBeInTheDocument();
    expect(screen.getByText(/dados de 25\/11\/2026/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Código e instruções/ })).toHaveAttribute(
      "href",
      "https://github.com/JH-2002/climate-platform",
    );
  });
});
