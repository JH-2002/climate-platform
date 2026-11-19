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
