"use client";

import { useOnline } from "@/features/offline/useOnline";

export const OFFLINE_MESSAGE =
  "Sem conexão: você está vendo os últimos dados salvos neste aparelho. Os horários de cada dado continuam valendo.";

/** Faixa fixa sem conexão (spec 013, FR-204, BR-200). */
export function OfflineBannerView({ online }: { online: boolean }) {
  return (
    <div role="status" aria-live="polite">
      {!online && (
        <p className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-950 md:px-8">
          {OFFLINE_MESSAGE}
        </p>
      )}
    </div>
  );
}

export function OfflineBanner() {
  return <OfflineBannerView online={useOnline()} />;
}
