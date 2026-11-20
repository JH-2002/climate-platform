import { formatNumber } from "@/lib/format";

export const MONTHS_SHORT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

export function mm(value: unknown, digits = 1): string {
  return typeof value === "number" && Number.isFinite(value) ? `${formatNumber(value, digits)} mm` : "—";
}

export function num(value: unknown, digits = 1): string {
  return typeof value === "number" && Number.isFinite(value) ? formatNumber(value, digits) : "—";
}

export function pct(value: unknown, digits = 0): string {
  return typeof value === "number" && Number.isFinite(value) ? `${formatNumber(value * 100, digits)}%` : "—";
}

/** "2026-11-01" -> "nov/2026"; "2026-11-18" (diário) -> "18/11/2026"; "2026-01-01" (ano) -> "2026". */
export function periodLabel(iso: string, grain: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-");
  if (grain === "year") return y ?? iso;
  if (grain === "month") return `${MONTHS_SHORT[Number(m) - 1]}/${y}`;
  return `${d}/${m}/${y}`;
}

export function isoDay(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function yesterdayIso(now: Date = new Date()): string {
  const local = new Date(now.toLocaleString("en-US", { timeZone: "America/Sao_Paulo" }));
  local.setDate(local.getDate() - 1);
  const y = local.getFullYear();
  const m = String(local.getMonth() + 1).padStart(2, "0");
  const d = String(local.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}
