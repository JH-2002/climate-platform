/**
 * Notificações neste navegador (spec 009, FR-149). Funções puras sobre um armazenamento
 * injetável; só a camada `notifier` toca na API de Notificações do navegador.
 * Sem push: com o navegador fechado, nada chega (a tela indica o SMS 40199).
 */

import type { StorageLike } from "@/features/locations/store";
import type { ActiveAlerts } from "./types";

export type NotifyScope = "city" | "locations";

export interface NotificationSettings {
  enabled: boolean;
  scope: NotifyScope;
}

export interface Notice {
  key: string;
  title: string;
  body: string;
  href: string;
}

export const SETTINGS_KEY = "climate-platform:alertas:notificacoes:v1";
export const SEEN_KEY = "climate-platform:alertas:avisados:v1";
export const SETTINGS_EVENT = "climate-platform:alertas:notificacoes";
export const SEEN_LIMIT = 300;
export const DEFAULT_SETTINGS: NotificationSettings = { enabled: false, scope: "city" };

export function loadSettings(storage: StorageLike | null): NotificationSettings {
  if (!storage) return DEFAULT_SETTINGS;
  try {
    const parsed = JSON.parse(storage.getItem(SETTINGS_KEY) ?? "null") as Partial<NotificationSettings> | null;
    if (!parsed || typeof parsed !== "object") return DEFAULT_SETTINGS;
    return {
      enabled: parsed.enabled === true,
      scope: parsed.scope === "locations" ? "locations" : "city",
    };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveSettings(storage: StorageLike | null, settings: NotificationSettings): boolean {
  if (!storage) return false;
  try {
    storage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    return true;
  } catch {
    return false;
  }
}

export function loadSeen(storage: StorageLike | null): Set<string> {
  if (!storage) return new Set();
  try {
    const parsed = JSON.parse(storage.getItem(SEEN_KEY) ?? "[]") as unknown;
    return new Set(Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : []);
  } catch {
    return new Set();
  }
}

/** Guarda os mais recentes (limite de 300), para o armazenamento não crescer sem fim. */
export function saveSeen(storage: StorageLike | null, seen: Set<string>): void {
  if (!storage) return;
  try {
    storage.setItem(SEEN_KEY, JSON.stringify([...seen].slice(-SEEN_LIMIT)));
  } catch {
    // modo privado ou cota: a sessão atual continua evitando repetições pela memória
  }
}

/** Chaves de tudo o que já está na tela: ao ligar, não avisa o que já estava lá. */
export function currentKeys(active: ActiveAlerts | undefined): string[] {
  return noticesFor(active, "city", null, new Set()).map((n) => n.key);
}

/**
 * O que avisar agora (AC-146): alertas oficiais vigentes ou próximos (da cidade, ou só os que
 * cobrem os locais salvos) e alertas do sistema em nível crítico. Cada um, uma única vez.
 */
export function noticesFor(
  active: ActiveAlerts | undefined,
  scope: NotifyScope,
  locationAlertIds: ReadonlySet<number> | null,
  seen: ReadonlySet<string>,
): Notice[] {
  if (!active) return [];
  const notices: Notice[] = [];
  for (const alert of active.official) {
    if (alert.status !== "ACTIVE" && alert.status !== "UPCOMING") continue;
    if (scope === "locations" && !locationAlertIds?.has(alert.id)) continue;
    const key = `oficial-${alert.id}`;
    if (seen.has(key)) continue;
    const when = alert.status === "UPCOMING" ? " (próximo)" : "";
    notices.push({
      key,
      title: `${alert.category_label}: ${alert.level_name ?? alert.severity_label}${when}`,
      body: alert.headline ?? alert.event ?? "Novo alerta oficial.",
      href: `/alerts?alerta=${alert.id}#alerta-${alert.id}`,
    });
  }
  for (const alert of active.system) {
    if (alert.category !== "RISK_ESTIMATE" || alert.level !== "CRITICAL") continue;
    const key = `sistema-${alert.id}-CRITICAL`;
    if (seen.has(key)) continue;
    notices.push({
      key,
      title: alert.title,
      body: alert.message,
      href: "/alerts#estimativa",
    });
  }
  return notices;
}

export type PermissionState = "unsupported" | "default" | "granted" | "denied";

export function permissionState(): PermissionState {
  if (typeof window === "undefined" || !("Notification" in window)) return "unsupported";
  return window.Notification.permission as PermissionState;
}
