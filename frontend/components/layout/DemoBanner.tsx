"use client";

import { useQuery } from "@tanstack/react-query";
import { demoEnabled, demoUrl } from "@/lib/demo";
import { formatDateTime } from "@/lib/format";

export const REPOSITORY_URL = "https://github.com/JH-2002/climate-platform";

export interface DemoMeta {
  recorded_at: string;
}

/** Faixa fixa da vitrine pública (spec 012, FR-192, BR-190). Fora do modo demonstração não aparece. */
export function DemoBannerView({ meta }: { meta: DemoMeta | null | undefined }) {
  return (
    <div className="border-b border-violet-300 bg-violet-50 px-4 py-2 text-sm text-violet-950 md:px-8">
      <p className="mx-auto max-w-6xl">
        <strong>Demonstração pública</strong>
        {meta?.recorded_at ? <> · dados de {formatDateTime(meta.recorded_at)}</> : null} · sem servidor: relatórios e
        simulações com valores livres ficam desligados.{" "}
        <a href={REPOSITORY_URL} className="font-medium underline">
          Código e instruções para rodar a plataforma
        </a>
      </p>
    </div>
  );
}

export function DemoBanner() {
  const enabled = demoEnabled();
  const { data } = useQuery({
    queryKey: ["demo-meta"],
    enabled,
    staleTime: Infinity,
    queryFn: async (): Promise<DemoMeta | null> => {
      const response = await fetch(demoUrl("meta.json"));
      return response.ok ? ((await response.json()) as DemoMeta) : null;
    },
  });
  if (!enabled) return null;
  return <DemoBannerView meta={data} />;
}
