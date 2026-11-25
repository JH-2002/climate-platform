/** Espelha `app.services.sources.SourceStatus` do backend. */
export type Freshness = "FRESH" | "DELAYED" | "STALE" | "UNAVAILABLE" | "UNKNOWN";
export type FreshnessReason =
  | "ok"
  | "delayed"
  | "stale"
  | "missing_credentials"
  | "last_run_failed"
  | "never_collected"
  | "disabled";

export interface SourceStatus {
  code: string;
  name: string;
  owner: string;
  url: string;
  license: string;
  attribution: string;
  access_method: string;
  expected_interval_s: number;
  freshness: Freshness;
  reason: FreshnessReason;
  last_success_at: string | null;
  last_attempt_at: string | null;
  last_run_status: string | null;
  last_error: string | null;
}

export interface SourceStatusList {
  checked_at: string;
  items: SourceStatus[];
}

export const FRESHNESS_LABELS: Record<Freshness, string> = {
  FRESH: "Atualizado",
  DELAYED: "Atrasado",
  STALE: "Desatualizado",
  UNAVAILABLE: "Indisponível",
  UNKNOWN: "Sem coleta ainda",
};

export const REASON_LABELS: Record<FreshnessReason, string> = {
  ok: "Coleta dentro do intervalo esperado",
  delayed: "Última coleta passou do intervalo esperado",
  stale: "Dados antigos — coleta muito atrasada",
  missing_credentials: "Credencial (token) não configurada",
  last_run_failed: "A última tentativa de coleta falhou",
  never_collected: "Ainda não houve coleta",
  disabled: "Fonte desativada",
};
