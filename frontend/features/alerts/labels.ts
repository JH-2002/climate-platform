/** Textos, ordem e escolhas de exibição dos alertas (spec 009). Funções puras. */

import { formatDateTime } from "@/lib/format";
import type { ActiveAlerts, AlertCategory, OfficialAlert, OfficialStatus, SystemAlert } from "./types";

export const CATEGORY_TITLES: Record<AlertCategory, string> = {
  CIVIL_DEFENSE: "Alerta oficial — Defesa Civil",
  WEATHER_WARNING: "Aviso meteorológico oficial — INMET",
  RISK_ESTIMATE: "Estimativa do sistema — não é alerta oficial",
  DATA_QUALITY: "Qualidade dos dados",
};

export const STATUS_LABELS: Record<OfficialStatus, string> = {
  ACTIVE: "Vigente",
  UPCOMING: "Próximo",
  EXPIRED: "Encerrado",
  CANCELLED: "Cancelado pela fonte",
  SUPERSEDED: "Substituído pela fonte",
};

/** Ícone + texto: a severidade nunca é comunicada só pela cor (Constituição §11). */
export const SEVERITY_ICONS: Record<string, string> = {
  Extreme: "⛔",
  Severe: "▲",
  Moderate: "●",
  Minor: "○",
};

export function severityIcon(severity: string | null): string {
  return SEVERITY_ICONS[severity ?? ""] ?? "?";
}

const SEVERITY_RANK: Record<string, number> = { Extreme: 4, Severe: 3, Moderate: 2, Minor: 1 };

export function severityRank(severity: string | null): number {
  return SEVERITY_RANK[severity ?? ""] ?? 0;
}

export function validityText(alert: Pick<OfficialAlert, "onset_at" | "expires_at">): string {
  const start = alert.onset_at ? formatDateTime(alert.onset_at) : null;
  const end = alert.expires_at ? formatDateTime(alert.expires_at) : null;
  if (start && end) return `De ${start} até ${end}`;
  if (end) return `Até ${end}`;
  if (start) return `A partir de ${start}`;
  return "Vigência não informada pela fonte";
}

const SPECIAL_NAMES: Record<string, string> = { SE: "Sé", "M BOI MIRIM": "M'Boi Mirim" };
const LOWER = new Set(["DE", "DO", "DA", "DOS", "DAS", "E"]);

export function subprefectureName(name: string): string {
  if (SPECIAL_NAMES[name]) return SPECIAL_NAMES[name];
  return name
    .split(" ")
    .map((word, i) =>
      i > 0 && LOWER.has(word)
        ? word.toLowerCase()
        : word
            .split("-")
            .map((p) => p.charAt(0) + p.slice(1).toLowerCase())
            .join("-"),
    )
    .join(" ");
}

export function areaText(alert: OfficialAlert): string {
  if (alert.area_approximate) return "Área aproximada (limite da cidade ainda não carregado).";
  const n = alert.subprefectures.length;
  if (n === 0) return "Atinge a cidade em área pequena, sem cobrir 5% de nenhuma subprefeitura.";
  const pct = alert.city_fraction == null ? "" : ` (${Math.round(alert.city_fraction * 100)}% da área da cidade)`;
  if (n >= 32) {
    return alert.city_fraction == null || alert.city_fraction >= 0.99
      ? "Atinge toda a cidade."
      : `Atinge as 32 subprefeituras${pct}.`;
  }
  const names = alert.subprefectures.map(subprefectureName);
  return `Subprefeituras atingidas${pct}: ${names.join(", ")}.`;
}

export function officialByCategory(active: ActiveAlerts | undefined, category: OfficialAlert["category"]): OfficialAlert[] {
  return (active?.official ?? []).filter((a) => a.category === category);
}

export function systemByCategory(active: ActiveAlerts | undefined, category: SystemAlert["category"]): SystemAlert[] {
  return (active?.system ?? []).filter((a) => a.category === category);
}

/**
 * O alerta da faixa global (FR-147): o oficial vigente mais importante — Defesa Civil antes
 * do INMET, e depois a maior severidade. Próximos não entram na faixa.
 */
export function bannerAlert(active: ActiveAlerts | undefined): OfficialAlert | null {
  const current = (active?.official ?? []).filter((a) => a.status === "ACTIVE");
  if (current.length === 0) return null;
  return [...current].sort(
    (a, b) =>
      Number(b.category === "CIVIL_DEFENSE") - Number(a.category === "CIVIL_DEFENSE") ||
      severityRank(b.severity) - severityRank(a.severity) ||
      (b.onset_at ?? "").localeCompare(a.onset_at ?? ""),
  )[0]!;
}

export function officialActiveCount(active: ActiveAlerts | undefined): number {
  return active?.counts.official_active ?? 0;
}

export const LEVEL_LABELS: Record<string, string> = { CRITICAL: "Crítico", HIGH: "Alto", WARNING: "Aviso" };

export function alertHref(id: number): string {
  return `/alerts?alerta=${id}#alerta-${id}`;
}
