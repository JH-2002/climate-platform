export const DISPLAY_TIME_ZONE = "America/Sao_Paulo";

/** Formata um timestamp ISO-8601 em UTC para exibição no horário de São Paulo. */
export function formatDateTime(iso: string, timeZone: string = DISPLAY_TIME_ZONE): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "data inválida";
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

export function formatLatency(ms: number | null): string {
  if (ms === null) return "—";
  return `${ms.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ms`;
}

export function formatNumber(value: number | null, digits = 1): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return value.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function formatHour(iso: string, timeZone: string = DISPLAY_TIME_ZONE): string {
  return new Intl.DateTimeFormat("pt-BR", { timeZone, hour: "2-digit", minute: "2-digit" }).format(
    new Date(iso),
  );
}

/** "YYYY-MM-DD" (dia local) → "qui., 19/11". */
export function formatDay(isoDate: string): string {
  const date = new Date(`${isoDate}T12:00:00-03:00`);
  if (Number.isNaN(date.getTime())) return isoDate;
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: DISPLAY_TIME_ZONE,
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
  }).format(date);
}
