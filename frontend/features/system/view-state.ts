import type { ReadinessReport, ReadinessViewState } from "./types";

export interface ReadinessQueryState {
  isPending: boolean;
  isError: boolean;
  data: ReadinessReport | undefined;
  online: boolean;
}

/** Converte o estado da consulta nos estados de interface exigidos pela spec 001 (página /status). */
export function deriveReadinessViewState(state: ReadinessQueryState): ReadinessViewState {
  if (!state.online) return "offline";
  if (state.isError && !state.data) return "error";
  if (state.isPending && !state.data) return "loading";
  if (!state.data) return "error";
  return state.data.status === "ok" ? "success" : "degraded";
}
