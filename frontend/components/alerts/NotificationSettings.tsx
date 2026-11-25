"use client";

import { useState } from "react";
import { currentKeys, loadSeen, saveSeen, type NotifyScope } from "@/features/alerts/notifications";
import type { ActiveAlerts } from "@/features/alerts/types";
import { browserStorage, useNotificationSettings } from "@/features/alerts/useNotifications";

const SCOPES: { value: NotifyScope; label: string }[] = [
  { value: "city", label: "Alertas oficiais para a cidade" },
  { value: "locations", label: "Só os que cobrem os meus locais salvos" },
];

/** Notificações neste navegador, ligadas só por escolha do usuário (FR-149). */
export function NotificationSettings({ active, officialChannel }: { active: ActiveAlerts | undefined; officialChannel: string }) {
  const { settings, permission, update, enable } = useNotificationSettings();
  const [scope, setScope] = useState<NotifyScope>(settings.scope);
  const [message, setMessage] = useState<string | null>(null);
  const on = settings.enabled && permission === "granted";

  async function turnOn() {
    setMessage(null);
    const result = await enable(scope);
    if (result === "granted") {
      // o que já está na tela não vira notificação: só o que surgir daqui em diante
      const storage = browserStorage();
      const seen = loadSeen(storage);
      for (const key of currentKeys(active)) seen.add(key);
      saveSeen(storage, seen);
      setMessage("Notificações ligadas neste navegador.");
    } else if (result === "denied") {
      setMessage("O navegador recusou a permissão. Para mudar, libere as notificações deste site nas configurações do navegador.");
    } else if (result === "unsupported") {
      setMessage("Este navegador não oferece notificações.");
    }
  }

  function changeScope(next: NotifyScope) {
    setScope(next);
    if (on) update({ enabled: true, scope: next });
  }

  return (
    <section aria-labelledby="notificacoes" className="space-y-3 rounded-lg border border-surface-border bg-surface p-4">
      <h2 id="notificacoes" className="text-lg font-semibold">
        Avisar neste navegador
      </h2>
      <p className="text-sm text-ink-muted">
        Com uma aba da plataforma aberta, o navegador avisa uma vez cada alerta oficial novo e cada
        estimativa do sistema que chegar a crítico. A escolha fica só neste navegador.
      </p>
      {permission === "unsupported" ? (
        <p className="text-sm">Este navegador não oferece notificações.</p>
      ) : (
        <>
          <fieldset className="space-y-1 text-sm">
            <legend className="font-medium">O que avisar</legend>
            {SCOPES.map((s) => (
              <label key={s.value} className="flex items-center gap-2">
                <input
                  type="radio"
                  name="escopo-notificacao"
                  value={s.value}
                  checked={scope === s.value}
                  onChange={() => changeScope(s.value)}
                />
                {s.label}
              </label>
            ))}
          </fieldset>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            {on ? (
              <>
                <span className="font-medium text-status-ok">✓ Ligado neste navegador</span>
                <button
                  type="button"
                  onClick={() => {
                    update({ enabled: false, scope });
                    setMessage("Notificações desligadas.");
                  }}
                  className="rounded-md border border-surface-border px-3 py-1.5 font-medium"
                >
                  Desligar
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => void turnOn()}
                className="rounded-md bg-accent px-3 py-1.5 font-medium text-white hover:bg-accent-strong"
              >
                Ligar notificações
              </button>
            )}
            {permission === "denied" && !message && (
              <span>As notificações deste site estão bloqueadas nas configurações do navegador.</span>
            )}
          </div>
          {message && (
            <p role="status" className="text-sm">
              {message}
            </p>
          )}
        </>
      )}
      <p className="text-sm text-ink-muted">
        Com o navegador fechado, nada chega por aqui. {officialChannel}
      </p>
    </section>
  );
}
