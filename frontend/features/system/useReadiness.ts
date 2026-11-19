"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchReadiness } from "./api";
import { useOnlineStatus } from "./useOnlineStatus";
import { deriveReadinessViewState } from "./view-state";

export const READINESS_REFRESH_MS = 30_000;

export function useReadiness() {
  const online = useOnlineStatus();
  const query = useQuery({
    queryKey: ["system", "readiness"],
    queryFn: ({ signal }) => fetchReadiness(signal),
    refetchInterval: READINESS_REFRESH_MS,
    retry: 1,
  });

  return {
    ...query,
    online,
    viewState: deriveReadinessViewState({
      isPending: query.isPending,
      isError: query.isError,
      data: query.data,
      online,
    }),
  };
}
