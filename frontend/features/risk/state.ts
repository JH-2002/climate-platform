/** Filtros e setor selecionado da página `/risk`, sincronizados com a URL. Funções puras. */

import { isRiskCategory } from "./categories";
import type { RiskCategory } from "./types";

export interface RiskFilters {
  category: RiskCategory | null;
  subprefecture: string | null;
  sectorId: number | null;
}

interface ParamsLike {
  get(name: string): string | null;
}

export function parseRiskFilters(params: ParamsLike): RiskFilters {
  const category = params.get("categoria");
  const subprefecture = params.get("subprefeitura")?.trim() || null;
  const sector = Number(params.get("setor"));
  return {
    category: isRiskCategory(category) ? category : null,
    subprefecture,
    sectorId: Number.isInteger(sector) && sector > 0 ? sector : null,
  };
}

export function serializeRiskFilters(filters: RiskFilters): string {
  const params = new URLSearchParams();
  if (filters.category) params.set("categoria", filters.category);
  if (filters.subprefecture) params.set("subprefeitura", filters.subprefecture);
  if (filters.sectorId) params.set("setor", String(filters.sectorId));
  return params.toString();
}

export function riskHref(sectorId: number): string {
  return `/risk?${serializeRiskFilters({ category: null, subprefecture: null, sectorId })}`;
}
