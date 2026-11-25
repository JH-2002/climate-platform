"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { browserStorage } from "@/features/alerts/useNotifications";
import { createReport, fetchReportTypes, fetchReports } from "./api";
import { addReportId, loadReportIds, saveReportIds } from "./storage";
import type { ReportFormat, ReportRequest, ReportType } from "./types";

export function useReportTypes() {
  return useQuery({
    queryKey: ["reports", "types"],
    queryFn: ({ signal }) => fetchReportTypes(signal),
    staleTime: Infinity,
  });
}

/** Ids guardados neste navegador; lidos depois de montar (HTML igual no servidor). */
export function useReportIds() {
  const [ids, setIds] = useState<string[]>([]);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- ids só do navegador, lidos depois de montar para o HTML estático e o do navegador serem iguais (spec 014)
  useEffect(() => setIds(loadReportIds(browserStorage())), []);
  const add = useCallback((id: string) => {
    setIds((current) => {
      const next = addReportId(current, id);
      saveReportIds(browserStorage(), next);
      return next;
    });
  }, []);
  return { ids, add };
}

export function isOpen(request: ReportRequest): boolean {
  return request.status === "QUEUED" || request.status === "RUNNING";
}

/** Andamento a cada 3 s enquanto houver pedido em aberto (FR-156). */
export function useReports(ids: string[]) {
  return useQuery({
    queryKey: ["reports", "list", ids.join(",")],
    queryFn: ({ signal }) => fetchReports(ids, signal),
    enabled: ids.length > 0,
    refetchInterval: (query) => (query.state.data?.some(isOpen) ? 3000 : false),
  });
}

export function useCreateReport(onCreated: (request: ReportRequest) => void) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { type: ReportType; format: ReportFormat; params: Record<string, unknown> }) =>
      createReport(input.type, input.format, input.params),
    onSuccess: (request) => {
      onCreated(request);
      void client.invalidateQueries({ queryKey: ["reports", "list"] });
    },
  });
}
