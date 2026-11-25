import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AlertBannerView } from "@/components/alerts/AlertBanner";
import { AlertHistoryTable } from "@/components/alerts/AlertHistory";
import { AlertNotifier } from "@/components/alerts/AlertNotifier";
import { AlertsNowCardView } from "@/components/alerts/AlertsNowCard";
import { AlertsPageView } from "@/components/alerts/AlertsPageView";
import { NotificationSettings } from "@/components/alerts/NotificationSettings";
import { historyQuery } from "@/features/alerts/api";
import { areaText, bannerAlert, subprefectureName, validityText } from "@/features/alerts/labels";
import {
  SEEN_KEY,
  SEEN_LIMIT,
  SETTINGS_KEY,
  loadSeen,
  loadSettings,
  noticesFor,
  saveSeen,
} from "@/features/alerts/notifications";
import { activeAlerts, inmetWarning, official, qualityAlert, riskAlert } from "./alertsFixtures";
import { renderWithQuery } from "./query";

async function seriousViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { region: { enabled: false } } });
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

function memoryStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    data,
  };
}

describe("textos e escolhas dos alertas", () => {
  it("a faixa mostra a Defesa Civil antes do INMET e só alertas vigentes", () => {
    const severeInmet = { ...inmetWarning, status: "ACTIVE" as const };
    expect(bannerAlert(activeAlerts({ official: [severeInmet, official()] }))?.id).toBe(1);
    expect(bannerAlert(activeAlerts({ official: [inmetWarning] }))).toBeNull(); // próximo não entra
    const extreme = official({ id: 9, severity: "Extreme" });
    expect(bannerAlert(activeAlerts({ official: [official(), extreme] }))?.id).toBe(9);
    expect(bannerAlert(undefined)).toBeNull();
  });

  it("área, vigência e nomes", () => {
    expect(areaText(official())).toBe("Subprefeituras atingidas (21% da área da cidade): Lapa, Pinheiros, Sé.");
    expect(areaText(inmetWarning)).toBe("Atinge toda a cidade.");
    expect(areaText({ ...inmetWarning, city_fraction: 0.81 })).toBe("Atinge as 32 subprefeituras (81% da área da cidade).");
    expect(areaText(official({ area_approximate: true }))).toMatch(/aproximada/);
    expect(validityText({ onset_at: null, expires_at: null })).toBe("Vigência não informada pela fonte");
    expect(validityText(official())).toMatch(/^De 24\/11\/2026/);
    expect(subprefectureName("CASA VERDE-CACHOEIRINHA")).toBe("Casa Verde-Cachoeirinha");
    expect(subprefectureName("CIDADE DE DEUS")).toBe("Cidade de Deus");
    expect(historyQuery("WEATHER_WARNING", 2)).toBe("/api/v1/alerts?pagina=2&categoria=WEATHER_WARNING");
  });
});

describe("página de alertas (FR-146, BR-140, BR-144)", () => {
  it("separa as categorias, com os rótulos e o texto oficial", async () => {
    const { container } = render(<AlertsPageView active={activeAlerts({ system: [riskAlert, qualityAlert] })} selectedId={1} />);
    const civil = screen.getByRole("region", { name: "Alerta oficial — Defesa Civil" });
    expect(within(civil).getByText(/Zonas Oeste e Sul de Sao Paulo/)).toBeTruthy();
    expect(within(civil).getByText("Em caso de emergência, ligue 199 ou 193.")).toBeTruthy();
    expect(within(civil).getByText("Vigente")).toBeTruthy();
    const inmet = screen.getByRole("region", { name: "Aviso meteorológico oficial — INMET" });
    expect(within(inmet).getByText(/Laranja — Perigo/)).toBeTruthy();
    expect(within(inmet).getByText("Próximo")).toBeTruthy();
    const estimate = screen.getByRole("region", { name: "Estimativa do sistema — não é alerta oficial" });
    expect(within(estimate).getByText("Estimativa do sistema: risco crítico em Penha")).toBeTruthy();
    expect(within(estimate).queryByText(/Defesa Civil:/)).toBeNull();
    const quality = screen.getByRole("region", { name: "Qualidade dos dados" });
    expect(within(quality).getByText("Fonte atrasada: avisos do INMET")).toBeTruthy();
    expect(container.querySelector("#alerta-1")?.className).toMatch(/ring-2/);
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("sem alertas e com as fontes em dia, diz que não há; com fonte parada, não afirma", () => {
    const { rerender } = render(<AlertsPageView active={activeAlerts({ official: [], system: [] })} selectedId={null} />);
    expect(screen.getByText("Nenhum alerta da Defesa Civil vigente ou previsto para a cidade agora.")).toBeTruthy();
    const stale = activeAlerts({
      official: [],
      system: [],
      sources_ok: false,
      sources: activeAlerts().sources.map((s) => (s.code === "idap-alerts" ? { ...s, freshness: "STALE" } : s)),
    });
    rerender(<AlertsPageView active={stale} selectedId={null} />);
    expect(screen.getByText(/não dá para afirmar que não há alerta da Defesa Civil/)).toBeTruthy();
    expect(screen.getByText(/a ausência de alertas aqui não quer dizer/)).toBeTruthy();
    expect(screen.getByText("Nenhum aviso do INMET vigente ou previsto para a cidade agora.")).toBeTruthy();
  });

  it("histórico com links para os alertas oficiais", () => {
    render(
      <AlertHistoryTable
        history={{
          items: [
            {
              kind: "official",
              id: 1,
              category: "CIVIL_DEFENSE",
              category_label: "Alerta oficial — Defesa Civil",
              title: "Chuva na Zona Oeste",
              level: "Moderate",
              level_label: "Moderada",
              start_at: "2026-11-24T19:19:13Z",
              end_at: "2026-11-25T02:30:00Z",
              status: "EXPIRED",
            },
            {
              kind: "system",
              id: 3,
              category: "RISK_ESTIMATE",
              category_label: "Estimativa do sistema — não é alerta oficial",
              title: "Estimativa do sistema: risco alto em Penha",
              level: "HIGH",
              level_label: "Alto",
              start_at: "2026-11-24T18:00:00Z",
              end_at: null,
              status: "OPEN",
            },
          ],
          total: 2,
          page: 1,
          page_size: 50,
          since: "2026-11-17T20:00:00Z",
          until: "2026-11-24T20:00:00Z",
        }}
      />,
    );
    expect(screen.getByRole("link", { name: "Chuva na Zona Oeste" }).getAttribute("href")).toBe("/alerts?alerta=1#alerta-1");
    expect(screen.getByText("Encerrado")).toBeTruthy();
    expect(screen.getByText("em aberto")).toBeTruthy();
  });
});

describe("faixa global (FR-147, AC-145)", () => {
  it("mostra fonte e severidade e anuncia uma vez cada alerta novo", () => {
    const active = activeAlerts();
    const { rerender } = render(<AlertBannerView active={active} />);
    const live = screen.getByRole("alert");
    expect(live.textContent).toMatch(/^Alerta oficial — Defesa Civil: Defesa Civil:16:15/);
    expect(screen.getByText("· severidade moderada")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Ver alerta" }).getAttribute("href")).toBe("/alerts?alerta=1#alerta-1");
    // nova consulta com o mesmo alerta: o anúncio não muda
    rerender(<AlertBannerView active={activeAlerts()} />);
    expect(screen.getByRole("alert").textContent).toBe(live.textContent);
    const next = official({ id: 2, headline: "Novo alerta na Zona Norte" });
    rerender(<AlertBannerView active={activeAlerts({ official: [next] })} />);
    expect(screen.getByRole("alert").textContent).toMatch(/Novo alerta na Zona Norte/);
  });

  it("sem alerta vigente, não há faixa", () => {
    render(<AlertBannerView active={activeAlerts({ official: [inmetWarning] })} />);
    expect(screen.queryByRole("link", { name: /Ver alerta/ })).toBeNull();
  });
});

describe("cartão Alertas agora (FR-148)", () => {
  it("oficiais primeiro e a estimativa separada", () => {
    render(<AlertsNowCardView active={activeAlerts()} />);
    expect(screen.getAllByRole("link", { name: "detalhes" })).toHaveLength(2);
    expect(screen.getByText(/não é alerta oficial\): risco alto ou crítico em 1 subprefeitura/)).toBeTruthy();
  });

  it("com fonte parada, não diz que não há alerta", () => {
    render(<AlertsNowCardView active={activeAlerts({ official: [], sources_ok: false })} />);
    expect(screen.getByText(/não dá para afirmar que não há alerta oficial agora/)).toBeTruthy();
    expect(screen.queryByText(/Nenhum alerta oficial/)).toBeNull();
  });
});

describe("notificações (FR-149, AC-146)", () => {
  it("cada alerta, uma vez; escopo dos locais; sistema só em crítico", () => {
    const active = activeAlerts({ system: [riskAlert, { ...riskAlert, id: 5, level: "HIGH" }] });
    const all = noticesFor(active, "city", null, new Set());
    expect(all.map((n) => n.key)).toEqual(["oficial-1", "oficial-7", "sistema-3-CRITICAL"]);
    expect(all[1]!.title).toBe("Aviso meteorológico oficial — INMET: Laranja — Perigo (próximo)");
    expect(noticesFor(active, "city", null, new Set(["oficial-1", "oficial-7"])).map((n) => n.key)).toEqual([
      "sistema-3-CRITICAL",
    ]);
    const onlyMine = noticesFor(active, "locations", new Set([7]), new Set());
    expect(onlyMine.map((n) => n.key)).toEqual(["oficial-7", "sistema-3-CRITICAL"]);
    const expired = activeAlerts({ official: [official({ status: "EXPIRED" })], system: [] });
    expect(noticesFor(expired, "city", null, new Set())).toEqual([]);
  });

  it("armazenamento tolerante e com limite", () => {
    const storage = memoryStorage({ [SETTINGS_KEY]: "{quebrado", [SEEN_KEY]: '["a", 3]' });
    expect(loadSettings(storage)).toEqual({ enabled: false, scope: "city" });
    expect([...loadSeen(storage)]).toEqual(["a"]);
    saveSeen(storage, new Set(Array.from({ length: SEEN_LIMIT + 20 }, (_, i) => `k${i}`)));
    const saved = JSON.parse(storage.data.get(SEEN_KEY)!) as string[];
    expect(saved).toHaveLength(SEEN_LIMIT);
    expect(saved[0]).toBe("k20");
  });
});

describe("notificações no navegador", () => {
  const created: { title: string; options: NotificationOptions }[] = [];

  class FakeNotification {
    static permission: NotificationPermission = "default";
    static requestPermission = vi.fn(async () => {
      FakeNotification.permission = "granted";
      return "granted" as NotificationPermission;
    });
    onclick: (() => void) | null = null;
    constructor(title: string, options: NotificationOptions) {
      created.push({ title, options });
    }
  }

  beforeEach(() => {
    created.length = 0;
    window.localStorage.clear();
    FakeNotification.permission = "default";
    vi.stubGlobal("Notification", FakeNotification);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("ligar pede a permissão e não avisa o que já estava na tela", async () => {
    render(<NotificationSettings active={activeAlerts()} officialChannel="SMS 40199." />);
    await waitFor(() => screen.getByRole("button", { name: "Ligar notificações" }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Ligar notificações" }));
    });
    expect(FakeNotification.requestPermission).toHaveBeenCalled();
    expect(screen.getByText("Notificações ligadas neste navegador.")).toBeTruthy();
    expect(JSON.parse(window.localStorage.getItem(SETTINGS_KEY)!)).toEqual({ enabled: true, scope: "city" });
    expect([...loadSeen(window.localStorage)]).toEqual(["oficial-1", "oficial-7", "sistema-3-CRITICAL"]);
    expect(screen.getByRole("button", { name: "Desligar" })).toBeTruthy();
  });

  it("avisa um alerta novo uma única vez, mesmo depois de recarregar", async () => {
    FakeNotification.permission = "granted";
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify({ enabled: true, scope: "city" }));
    const seed: [unknown[], unknown][] = [[["alerts", "active"], activeAlerts({ official: [official()], system: [] })]];
    const first = renderWithQuery(<AlertNotifier />, seed);
    await waitFor(() => expect(created).toHaveLength(1));
    expect(created[0]!.title).toBe("Alerta oficial — Defesa Civil: Moderada");
    expect(created[0]!.options.tag).toBe("oficial-1");
    first.unmount();
    renderWithQuery(<AlertNotifier />, seed); // "recarregar a página"
    await new Promise((r) => setTimeout(r, 20));
    expect(created).toHaveLength(1);
  });

  it("desligado, não avisa", async () => {
    FakeNotification.permission = "granted";
    renderWithQuery(<AlertNotifier />, [[["alerts", "active"], activeAlerts()]]);
    await new Promise((r) => setTimeout(r, 20));
    expect(created).toHaveLength(0);
  });
});
