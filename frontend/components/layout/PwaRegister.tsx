"use client";

import { useEffect } from "react";
import { basePath } from "@/lib/demo";

/** URL de registro do service worker, com o prefixo do site (vitrine no GitHub Pages). */
export function serviceWorkerUrl(base: string): { url: string; scope: string } {
  const prefix = base.replace(/\/+$/, "");
  return { url: `${prefix}/sw.js?base=${encodeURIComponent(prefix)}`, scope: `${prefix}/` };
}

/** Registra o service worker só no build de produção (spec 013, FR-203). */
export function PwaRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    const { url, scope } = serviceWorkerUrl(basePath());
    navigator.serviceWorker.register(url, { scope }).catch(() => undefined);
  }, []);
  return null;
}
