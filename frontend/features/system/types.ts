/** Espelha `app.core.health.ReadinessReport` do backend. */
export type ComponentStatus = "ok" | "unavailable";
export type OverallStatus = "ok" | "degraded";

export interface ComponentResult {
  status: ComponentStatus;
  latency_ms: number | null;
  detail: string | null;
  info: Record<string, string>;
}

export interface ReadinessReport {
  status: OverallStatus;
  checked_at: string;
  components: Record<string, ComponentResult>;
}

export type ReadinessViewState = "loading" | "success" | "degraded" | "error" | "offline";

export const COMPONENT_LABELS: Record<string, string> = {
  db: "Banco de dados (PostgreSQL)",
  postgis: "Extensão geoespacial (PostGIS)",
  redis: "Fila e cache (Redis)",
  worker: "Workers de processamento (Celery)",
};
