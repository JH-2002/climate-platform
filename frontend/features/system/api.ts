import { apiGet } from "@/lib/api-client";
import type { ReadinessReport } from "./types";

export async function fetchReadiness(
  signal?: AbortSignal,
  fetchImpl?: typeof fetch,
): Promise<ReadinessReport> {
  // O 503 traz um relatório válido indicando qual componente está fora do ar.
  const { data } = await apiGet<ReadinessReport>("/api/v1/health/ready", {
    signal,
    acceptStatuses: [503],
    fetchImpl,
  });
  return data;
}
