"use client";

import { useEffect } from "react";
import { useActiveAlerts, useAlertsAtLocations } from "@/features/alerts/hooks";
import { loadSeen, noticesFor, saveSeen } from "@/features/alerts/notifications";
import { browserStorage, useNotificationSettings } from "@/features/alerts/useNotifications";
import { useLocations } from "@/features/locations/useLocations";

/** Mostra as notificações do navegador para alertas novos (FR-149). Não desenha nada. */
export function AlertNotifier() {
  const { data } = useActiveAlerts();
  const { settings, permission } = useNotificationSettings();
  const { locations } = useLocations();
  const active = settings.enabled && permission === "granted";
  const atLocations = useAlertsAtLocations(locations, active && settings.scope === "locations");

  useEffect(() => {
    if (!active || !data) return;
    const ids =
      settings.scope === "locations"
        ? new Set(atLocations.byLocation.flatMap((entry) => entry.alerts.map((a) => a.id)))
        : null;
    const storage = browserStorage();
    const seen = loadSeen(storage);
    const notices = noticesFor(data, settings.scope, ids, seen);
    if (notices.length === 0) return;
    for (const notice of notices) {
      try {
        const n = new window.Notification(notice.title, { body: notice.body, tag: notice.key });
        n.onclick = () => {
          window.focus();
          window.location.assign(notice.href);
        };
      } catch {
        // navegador sem suporte a notificações fora de um service worker (alguns celulares)
      }
      seen.add(notice.key);
    }
    saveSeen(storage, seen);
  }, [active, data, settings.scope, atLocations.byLocation]);

  return null;
}
