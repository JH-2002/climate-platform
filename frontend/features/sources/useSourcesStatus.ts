"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchSourcesStatus } from "./api";

export function useSourcesStatus() {
  return useQuery({
    queryKey: ["sources", "status"],
    queryFn: ({ signal }) => fetchSourcesStatus(signal),
    refetchInterval: 60_000,
    retry: 1,
  });
}
