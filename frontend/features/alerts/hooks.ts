"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import type { SavedLocation } from "@/features/locations/store";
import { fetchActiveAlerts, fetchAlertHistory, fetchAlertsAt, fetchAlertsLayer, fetchOfficialAlert } from "./api";
import type { AlertCategory } from "./types";

/** Com uma aba aberta, os alertas são consultados a cada 2 min (FR-149). */
export const ALERTS_REFRESH_MS = 2 * 60_000;

export function useActiveAlerts() {
  return useQuery({
    queryKey: ["alerts", "active"],
    queryFn: ({ signal }) => fetchActiveAlerts(signal),
    refetchInterval: ALERTS_REFRESH_MS,
    refetchIntervalInBackground: true,
  });
}

export function useAlertHistory(category: AlertCategory | null, page: number) {
  return useQuery({
    queryKey: ["alerts", "history", category, page],
    queryFn: ({ signal }) => fetchAlertHistory(category, page, signal),
    refetchInterval: 10 * 60_000,
  });
}

export function useOfficialAlert(id: number | null) {
  return useQuery({
    queryKey: ["alerts", "official", id],
    queryFn: ({ signal }) => fetchOfficialAlert(id as number, signal),
    enabled: id !== null,
    retry: (count, error) => count < 1 && !("status" in error && error.status === 404),
  });
}

export function useAlertsLayer(enabled = true) {
  return useQuery({
    queryKey: ["map", "alerts"],
    queryFn: ({ signal }) => fetchAlertsLayer(signal),
    enabled,
    refetchInterval: ALERTS_REFRESH_MS,
  });
}

/** Alertas oficiais que cobrem cada local salvo (até 10 locais). */
export function useAlertsAtLocations(locations: SavedLocation[], enabled: boolean) {
  const list = locations.slice(0, 10);
  return useQueries({
    queries: list.map((loc) => ({
      queryKey: ["alerts", "at", loc.lat.toFixed(4), loc.lon.toFixed(4)],
      queryFn: ({ signal }: { signal: AbortSignal }) => fetchAlertsAt(loc.lat, loc.lon, signal),
      enabled,
      refetchInterval: ALERTS_REFRESH_MS,
    })),
    combine: (results) => ({
      byLocation: list.map((loc, i) => ({ location: loc, alerts: results[i]?.data ?? [] })),
      isError: results.some((r) => r.isError),
    }),
  });
}
