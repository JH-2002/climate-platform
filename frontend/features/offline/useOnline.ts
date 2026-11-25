"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

/** Estado da conexão do aparelho (spec 013, FR-204). Ao voltar a conexão, refaz as consultas. */
export function useOnline(): boolean {
  const [online, setOnline] = useState(true);
  const queryClient = useQueryClient();

  useEffect(() => {
    setOnline(navigator.onLine);
    const goOnline = () => {
      setOnline(true);
      void queryClient.refetchQueries({ type: "active" });
    };
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, [queryClient]);

  return online;
}
