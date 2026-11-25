"use client";

import { useSyncExternalStore } from "react";
import { prefersReducedMotion, supportsWebGL } from "./capabilities";

/*
 * Capacidades do navegador como valores externos (spec 014): no HTML estático e no servidor
 * valem "desconhecido"; no navegador, o valor real, sem setState dentro de efeito.
 */

const never = () => () => undefined;
let webglCache: boolean | null = null;

function webglSnapshot(): boolean {
  webglCache ??= supportsWebGL();
  return webglCache;
}

/** null enquanto não se sabe (servidor e primeira renderização). */
export function useWebGL(): boolean | null {
  return useSyncExternalStore(never, webglSnapshot, () => null);
}

const MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeMotion(onChange: () => void): () => void {
  const media = window.matchMedia?.(MOTION_QUERY);
  media?.addEventListener?.("change", onChange);
  return () => media?.removeEventListener?.("change", onChange);
}

export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribeMotion, () => prefersReducedMotion(), () => false);
}
