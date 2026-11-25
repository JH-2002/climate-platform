import { apiGet } from "@/lib/api-client";
import type { SourceStatusList } from "./types";

export async function fetchSourcesStatus(
  signal?: AbortSignal,
  fetchImpl?: typeof fetch,
): Promise<SourceStatusList> {
  const { data } = await apiGet<SourceStatusList>("/api/v1/sources/status", { signal, fetchImpl });
  return data;
}
