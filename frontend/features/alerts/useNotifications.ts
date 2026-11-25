"use client";

import { useCallback, useEffect, useState } from "react";
import type { StorageLike } from "@/features/locations/store";
import {
  DEFAULT_SETTINGS,
  SETTINGS_EVENT,
  loadSettings,
  permissionState,
  saveSettings,
  type NotificationSettings,
  type PermissionState,
} from "./notifications";

export function browserStorage(): StorageLike | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** Escolha de notificações, compartilhada entre a página e o observador do layout. */
export function useNotificationSettings() {
  const [settings, setSettings] = useState<NotificationSettings>(DEFAULT_SETTINGS);
  const [permission, setPermission] = useState<PermissionState>("unsupported");

  useEffect(() => {
    const sync = () => {
      setSettings(loadSettings(browserStorage()));
      setPermission(permissionState());
    };
    sync();
    window.addEventListener(SETTINGS_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(SETTINGS_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const update = useCallback((next: NotificationSettings) => {
    saveSettings(browserStorage(), next);
    setSettings(next);
    window.dispatchEvent(new Event(SETTINGS_EVENT));
  }, []);

  /** Pede a permissão do navegador (só a partir de um clique) e liga se o usuário aceitar. */
  const enable = useCallback(
    async (scope: NotificationSettings["scope"]) => {
      if (permissionState() === "unsupported") return "unsupported" as const;
      const result = (await window.Notification.requestPermission()) as PermissionState;
      setPermission(result);
      if (result === "granted") update({ enabled: true, scope });
      return result;
    },
    [update],
  );

  return { settings, permission, update, enable };
}
