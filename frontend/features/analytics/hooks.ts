"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchInsights, fetchKpis } from "./api";

const REFRESH_MS = 5 * 60_000;

export function useKpis() {
  return useQuery({ queryKey: ["analytics", "kpis"], queryFn: ({ signal }) => fetchKpis(signal), refetchInterval: REFRESH_MS });
}

export function useInsights() {
  return useQuery({
    queryKey: ["analytics", "insights"],
    queryFn: ({ signal }) => fetchInsights(signal),
    refetchInterval: REFRESH_MS,
  });
}
