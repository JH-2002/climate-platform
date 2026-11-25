/** Ids dos pedidos feitos neste navegador (sem contas; spec 010, FR-152). Funções puras. */

import type { StorageLike } from "@/features/locations/store";

export const REPORTS_KEY = "climate-platform:relatorios:v1";
export const REPORTS_LIMIT = 50;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function loadReportIds(storage: StorageLike | null): string[] {
  if (!storage) return [];
  try {
    const parsed = JSON.parse(storage.getItem(REPORTS_KEY) ?? "[]") as unknown;
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string" && UUID.test(v)) : [];
  } catch {
    return [];
  }
}

/** O mais novo primeiro; até 50. */
export function addReportId(ids: string[], id: string): string[] {
  return [id, ...ids.filter((x) => x !== id)].slice(0, REPORTS_LIMIT);
}

export function saveReportIds(storage: StorageLike | null, ids: string[]): void {
  if (!storage) return;
  try {
    storage.setItem(REPORTS_KEY, JSON.stringify(ids));
  } catch {
    // modo privado ou cota: a lista vale só nesta aba
  }
}
