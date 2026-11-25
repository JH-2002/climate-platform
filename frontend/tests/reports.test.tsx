import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { ReportForm } from "@/components/reports/ReportForm";
import { ReportList } from "@/components/reports/ReportList";
import { ReportShortcut } from "@/components/reports/ReportShortcut";
import { apiParams, defaultForm, formFromUrl, formatBytes, reportHref } from "@/features/reports/form";
import { isOpen } from "@/features/reports/hooks";
import { REPORTS_KEY, REPORTS_LIMIT, addReportId, loadReportIds, saveReportIds } from "@/features/reports/storage";
import type { ReportForm as Form, ReportRequest, ReportTypeInfo } from "@/features/reports/types";

async function seriousViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { region: { enabled: false } } });
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

const TODAY = new Date("2026-11-25T12:00:00Z");
const ID = "4f9c2a8e-1b2d-4c3e-9f00-123456789abc";

const TYPES: ReportTypeInfo[] = [
  { code: "situacao", title: "Situação agora", description: "Alertas e risco agora.", formats: ["pdf", "csv", "json"], params: [] },
  {
    code: "risco",
    title: "Risco por setor",
    description: "Setores.",
    formats: ["pdf", "csv", "json"],
    params: [{ name: "subprefecture", label: "Subprefeitura", required: false, help: "" }],
  },
  {
    code: "alertas",
    title: "Alertas do período",
    description: "Alertas.",
    formats: ["pdf", "csv", "json"],
    params: [{ name: "since", label: "Desde", required: true, help: "" }],
  },
  {
    code: "chuva",
    title: "Chuva do período",
    description: "Chuva.",
    formats: ["pdf", "csv", "json"],
    params: [{ name: "since", label: "Desde", required: true, help: "" }],
  },
  {
    code: "simulacao",
    title: "Simulação",
    description: "Simulação.",
    formats: ["pdf", "csv", "json"],
    params: [{ name: "simulation_id", label: "Simulação", required: true, help: "" }],
  },
];

function request(overrides: Partial<ReportRequest> = {}): ReportRequest {
  return {
    id: ID,
    report_type: "risco",
    format: "csv",
    title: "Risco por setor — Município de São Paulo",
    params: {},
    mode: "REAL",
    status: "DONE",
    error: null,
    created_at: "2026-11-25T12:00:00Z",
    started_at: "2026-11-25T12:00:01Z",
    finished_at: "2026-11-25T12:00:03Z",
    expires_at: "2026-12-02T12:00:03Z",
    bytes: 182_400,
    filename: "risco_2026-11-25_0900.csv",
    download_url: `/api/v1/reports/${ID}/download`,
    ...overrides,
  };
}

describe("formulário pela URL e parâmetros da API", () => {
  it("atalhos preenchem o formulário; valores inválidos voltam ao padrão", () => {
    const form = formFromUrl(new URLSearchParams("tipo=risco&formato=csv&subprefeitura=PENHA"), TODAY);
    expect(form).toMatchObject({ type: "risco", format: "csv", subprefecture: "PENHA" });
    expect(apiParams(form)).toEqual({ subprefecture: "PENHA" });
    const bad = formFromUrl(new URLSearchParams("tipo=xyz&formato=doc&desde=ontem&agregacao=hora"), TODAY);
    expect(bad).toEqual(defaultForm(TODAY));
    expect(defaultForm(TODAY)).toMatchObject({ since: "2026-11-18", until: "2026-11-25" });
  });

  it("cada tipo manda só os seus parâmetros", () => {
    const base = defaultForm(TODAY);
    expect(apiParams({ ...base, type: "situacao", subprefecture: "PENHA" })).toEqual({});
    expect(apiParams({ ...base, type: "alertas", category: "CIVIL_DEFENSE" })).toEqual({
      since: "2026-11-18",
      until: "2026-11-25",
      category: "CIVIL_DEFENSE",
    });
    expect(apiParams({ ...base, type: "chuva", grain: "year" })).toEqual({
      since: "2026-11-18",
      until: "2026-11-25",
      grain: "year",
    });
    expect(apiParams({ ...base, type: "simulacao", simulationId: ID })).toEqual({ simulation_id: ID });
    expect(reportHref("simulacao", { simulacao: ID })).toBe(`/reports?tipo=simulacao&simulacao=${ID}`);
    expect(formatBytes(182_400)).toBe("178 KB");
    expect(formatBytes(3 * 1024 * 1024)).toBe("3,0 MB");
  });
});

describe("pedidos deste navegador", () => {
  it("guarda os ids, mais novo primeiro, com limite, e ignora lixo", () => {
    const data = new Map<string, string>();
    const storage = { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) };
    data.set(REPORTS_KEY, JSON.stringify([ID, "abc", 3]));
    expect(loadReportIds(storage)).toEqual([ID]);
    let ids: string[] = [];
    for (let i = 0; i < REPORTS_LIMIT + 5; i++) ids = addReportId(ids, `00000000-0000-4000-8000-${String(i).padStart(12, "0")}`);
    expect(ids).toHaveLength(REPORTS_LIMIT);
    expect(ids[0]).toMatch(/0054$/);
    saveReportIds(storage, ids);
    expect(loadReportIds(storage)).toEqual(ids);
    data.set(REPORTS_KEY, "{quebrado");
    expect(loadReportIds(storage)).toEqual([]);
  });

  it("lista com andamento, download e faixa de simulação (AC-156)", async () => {
    const { container } = render(
      <ReportList
        items={[
          request(),
          request({ id: "b", status: "RUNNING", download_url: null, filename: null, bytes: null }),
          request({ id: "c", status: "FAILED", error: "Simulação não encontrada.", download_url: null }),
          request({ id: "d", mode: "SIMULATION", title: "Simulação — 60 mm", status: "EXPIRED", download_url: null }),
        ]}
      />,
    );
    const link = screen.getByRole("link", { name: /Baixar risco_2026-11-25_0900.csv \(178 KB\)/ });
    expect(link.getAttribute("href")).toBe(`/api/v1/reports/${ID}/download`);
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.getByText("Gerando…")).toBeTruthy();
    expect(screen.getByText("Simulação não encontrada.")).toBeTruthy();
    expect(screen.getByText("SIMULAÇÃO")).toBeTruthy();
    expect(screen.getByText("Expirado (passou de 7 dias)")).toBeTruthy();
    expect(isOpen(request({ status: "QUEUED" }))).toBe(true);
    expect(isOpen(request())).toBe(false);
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("lista vazia", () => {
    render(<ReportList items={[]} />);
    expect(screen.getByText("Nenhum relatório pedido neste navegador ainda.")).toBeTruthy();
  });
});

function FormHarness({ onSubmit }: { onSubmit: (form: Form) => void }) {
  const [form, setForm] = useState<Form>(defaultForm(TODAY));
  return (
    <ReportForm
      types={TYPES}
      form={form}
      subprefectures={["PENHA", "SAO MIGUEL PAULISTA"]}
      points={[{ key: "-23.5700,-46.6200", label: "Centro (-23.5700,-46.6200)" }]}
      pending={false}
      error={null}
      onChange={setForm}
      onSubmit={() => onSubmit(form)}
    />
  );
}

describe("formulário (FR-156)", () => {
  it("mostra os parâmetros do tipo escolhido e envia", async () => {
    const onSubmit = vi.fn();
    const { container } = render(<FormHarness onSubmit={onSubmit} />);
    expect(screen.queryByLabelText("Subprefeitura")).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: /Risco por setor/ }));
    const select = screen.getByLabelText("Subprefeitura");
    expect(screen.getByRole("option", { name: "Sao Miguel Paulista" })).toBeTruthy();
    fireEvent.change(select, { target: { value: "PENHA" } });
    fireEvent.click(screen.getByRole("radio", { name: "CSV (planilha)" }));
    fireEvent.click(screen.getByRole("button", { name: "Gerar relatório" }));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ type: "risco", format: "csv", subprefecture: "PENHA" }));
    fireEvent.click(screen.getByRole("radio", { name: /Chuva do período/ }));
    expect(screen.getByLabelText("Agregação")).toBeTruthy();
    expect(screen.getByLabelText("Desde")).toBeTruthy();
    fireEvent.click(screen.getByRole("radio", { name: /Simulação/ }));
    expect(screen.getByLabelText("Id da simulação")).toBeTruthy();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("atalho aponta para a página preenchida", () => {
    render(<ReportShortcut type="risco" params={{ subprefeitura: "PENHA" }} />);
    expect(screen.getByRole("link", { name: /Gerar relatório/ }).getAttribute("href")).toBe(
      "/reports?tipo=risco&subprefeitura=PENHA",
    );
  });
});
