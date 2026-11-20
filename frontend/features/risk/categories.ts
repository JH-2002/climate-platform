/**
 * Categorias do risco estimado (BR-062): cor sempre com texto e ícone (Constituição §11).
 * Os rótulos nunca usam a palavra "alerta" (BR-065): risco estimado não é alerta oficial.
 */

import type { RiskCategory, RiskFactor } from "./types";

export interface CategoryInfo {
  label: string;
  /** Cor da categoria no mapa e no marcador do selo. */
  color: string;
  /** Fundo e texto do selo, com contraste AA. */
  background: string;
  text: string;
  /** Forma do ícone: muda junto com a cor, para quem não distingue cores. */
  shape: "circle" | "triangle" | "diamond" | "octagon" | "question";
  /** Altura da extrusão no mapa 3D, em metros. */
  height: number;
}

export const CATEGORY_ORDER: readonly RiskCategory[] = [
  "CRITICAL",
  "HIGH",
  "MODERATE",
  "LOW",
  "UNKNOWN",
];

export const CATEGORIES: Record<RiskCategory, CategoryInfo> = {
  LOW: { label: "Baixo", color: "#2e8b57", background: "#e3f4ea", text: "#14532d", shape: "circle", height: 40 },
  MODERATE: { label: "Moderado", color: "#e0b400", background: "#fdf3c7", text: "#6b4b00", shape: "triangle", height: 120 },
  HIGH: { label: "Alto", color: "#e8710a", background: "#fde5d0", text: "#7a2e05", shape: "diamond", height: 260 },
  CRITICAL: { label: "Crítico", color: "#c62828", background: "#fbdcdc", text: "#7f1d1d", shape: "octagon", height: 450 },
  UNKNOWN: { label: "Desconhecido", color: "#8a939b", background: "#eceff1", text: "#3d4650", shape: "question", height: 20 },
};

export function isRiskCategory(value: unknown): value is RiskCategory {
  return typeof value === "string" && value in CATEGORIES;
}

export function categoryLabel(category: string): string {
  return isRiskCategory(category) ? CATEGORIES[category].label : category;
}

export const RAIN_LEVEL_LABELS: Record<number, string> = {
  0: "Sem gatilho de chuva",
  1: "Chuva moderada",
  2: "Chuva forte",
  3: "Chuva muito forte",
};

export const SUSCEPTIBILITY_LABELS: Record<number, string> = {
  1: "Baixa",
  2: "Média",
  3: "Alta",
  4: "Muito alta",
};

export const KIND_LABELS: Record<string, string> = {
  FORECAST: "Previsão (modelo)",
  MODELED: "Estimativa de modelo",
  OBSERVED: "Registro oficial",
  DERIVED: "Calculado pelo sistema",
};

export const FACTOR_EFFECT_LABELS: Record<RiskFactor["effect"], string> = {
  raises: "Aumenta o risco",
  info: "Informativo",
  unknown: "Impede a estimativa",
};

export const OCCURRENCE_TYPE_LABELS: Record<string, string> = {
  ALAGAMENTO: "Alagamento",
  INUNDACAO: "Inundação",
};

/** Nomes da fonte vêm em maiúsculas e sem acento: só capitaliza ("SAO MIGUEL" -> "Sao Miguel"). */
export function titleCase(text: string | null): string {
  if (!text) return "—";
  const small = new Set(["da", "de", "do", "das", "dos", "e"]);
  return text
    .toLowerCase()
    .split(/\s+/)
    .map((word, i) => (i > 0 && small.has(word) ? word : word.charAt(0).toUpperCase() + word.slice(1)))
    .join(" ");
}
