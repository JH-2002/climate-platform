"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useSyncExternalStore } from "react";

function subscribe(onChange: () => void): () => void {
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

/** Estado da conexão do aparelho (spec 013, FR-204). Ao voltar a conexão, refaz as consultas. */
export function useOnline(): boolean {
  const online = useSyncExternalStore(subscribe, () => navigator.onLine, () => true);
  const queryClient = useQueryClient();

  useEffect(() => {
    const refetch = () => void queryClient.refetchQueries({ type: "active" });
    window.addEventListener("online", refetch);
    return () => window.removeEventListener("online", refetch);
  }, [queryClient]);

  return online;
}
