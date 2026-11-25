"use client";

import dynamic from "next/dynamic";
import { Suspense } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { BasinBlockView } from "@/components/geo/BasinBlockView";
import { BasinCard } from "@/components/geo/BasinCard";
import { BasinRanking } from "@/components/geo/BasinRanking";
import { ProfileChart } from "@/components/geo/ProfileChart";
import { useBasin, useBasins, useDemStatus, useGeoLayers, useProfile } from "@/features/geo/hooks";
import {
  MAX_PROFILE_POINTS,
  PROFILE_EXAMPLES,
  parseGeoState,
  serializeGeoState,
  type GeoState,
  type GeoTab,
} from "@/features/geo/state";

const GeoMap = dynamic(() => import("@/components/geo/GeoMap"), {
  ssr: false,
  loading: () => (
    <div role="status" className="h-[60vh] min-h-80 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
      <span className="sr-only">Carregando o mapa…</span>
    </div>
  ),
});

const TABS: { id: GeoTab; label: string }[] = [
  { id: "bacias", label: "Bacias" },
  { id: "perfil", label: "Perfil do relevo" },
  { id: "bloco", label: "Bloco 3D da bacia" },
];

function GeoPage() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const state = parseGeoState(params);
  const dem = useDemStatus();
  const layers = useGeoLayers();
  const basins = useBasins(state.sort);
  const basin = useBasin(state.basinId);
  const profile = useProfile(state.profile);

  function update(next: Partial<GeoState>) {
    router.replace(`${pathname}?${serializeGeoState({ ...state, ...next })}`, { scroll: false });
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Geointeligência 3D</h1>
        <p className="text-sm text-ink-muted">
          Bacias hidrográficas, rios e córregos, piscinões e relevo, junto com os setores de risco. O relevo é contexto:
          não muda a estimativa de risco e não desenha inundação.
        </p>
      </header>

      {dem.data && !dem.data.available && (
        <p role="status" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm">
          O relevo (Copernicus DEM, ~47 MB) ainda está sendo baixado pela primeira vez. Bacias, drenagem e piscinões já
          funcionam; elevação e perfil aparecem quando o download terminar.
        </p>
      )}

      <div role="tablist" aria-label="Seções da geointeligência" className="flex gap-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={state.tab === t.id}
            onClick={() => update({ tab: t.id })}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${state.tab === t.id ? "bg-accent text-white" : "border border-surface-border"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {state.tab !== "bloco" && (
      <GeoMap
        basins={layers.basins.data}
        reservoirs={layers.reservoirs.data}
        selectedBasinId={state.basinId}
        mode={state.tab === "perfil" ? "perfil" : "bacias"}
        profile={state.profile}
        onSelectBasin={(id) => update({ basinId: id })}
        onAddPoint={(lon, lat) =>
          state.profile.length < MAX_PROFILE_POINTS && update({ profile: [...state.profile, [lon, lat]] })
        }
      />
      )}

      {state.tab === "bloco" && (
        <div role="tabpanel" aria-label="Bloco 3D da bacia">
          <BasinBlockView
            basinId={state.basinId}
            simulationId={state.simulationId}
            basins={layers.basins.data}
            reservoirs={layers.reservoirs.data}
            onSimulation={(simulationId) => update({ simulationId })}
          />
        </div>
      )}

      {state.tab === "bacias" && (
        <div role="tabpanel" aria-label="Bacias" className="space-y-5">
          {basin.data && (
            <BasinCard
              detail={basin.data}
              onClose={() => update({ basinId: null })}
              onOpenBlock={() => update({ tab: "bloco" })}
            />
          )}
          {basin.isError && (
            <p role="alert" className="text-sm">
              Bacia não encontrada.
            </p>
          )}
          {basins.isPending && <p className="text-sm text-ink-muted">Carregando as bacias…</p>}
          {basins.isError && (
            <p role="alert" className="text-sm">
              Não foi possível carregar as bacias. {basins.error.message}
            </p>
          )}
          {basins.data &&
            (basins.data.items.length === 0 ? (
              <p className="text-sm text-ink-muted">
                As bacias do GeoSampa ainda não foram sincronizadas. A primeira sincronização acontece logo depois que o
                agendador inicia.
              </p>
            ) : (
              <BasinRanking
                list={basins.data}
                sort={state.sort}
                selectedId={state.basinId}
                onSort={(sort) => update({ sort })}
                onSelect={(id) => {
                  update({ basinId: id });
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              />
            ))}
        </div>
      )}

      {state.tab === "perfil" && (
        <div role="tabpanel" aria-label="Perfil do relevo" className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-ink-muted">Exemplos:</span>
            {PROFILE_EXAMPLES.map((ex) => (
              <button
                key={ex.label}
                type="button"
                onClick={() => update({ profile: ex.points })}
                className="rounded-full border border-surface-border px-3 py-1 hover:border-accent"
              >
                {ex.label}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span>
              {state.profile.length === 0
                ? "Nenhum ponto marcado."
                : `${state.profile.length} ponto(s) marcado(s).`}
            </span>
            <button
              type="button"
              disabled={state.profile.length === 0}
              onClick={() => update({ profile: state.profile.slice(0, -1) })}
              className="rounded-md border border-surface-border px-2 py-1 disabled:opacity-50"
            >
              Desfazer o último
            </button>
            <button
              type="button"
              disabled={state.profile.length === 0}
              onClick={() => update({ profile: [] })}
              className="rounded-md border border-surface-border px-2 py-1 disabled:opacity-50"
            >
              Limpar
            </button>
          </div>
          {state.profile.length === 1 && <p className="text-sm text-ink-muted">Marque mais um ponto para ver o perfil.</p>}
          {profile.isPending && state.profile.length >= 2 && (
            <div role="status" className="h-72 animate-pulse rounded-lg bg-surface-muted motion-reduce:animate-none">
              <span className="sr-only">Calculando o perfil…</span>
            </div>
          )}
          {profile.isError && (
            <p role="alert" className="rounded-lg border border-surface-border bg-surface p-3 text-sm">
              {profile.error.message}
            </p>
          )}
          {profile.data && <ProfileChart profile={profile.data} />}
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <GeoPage />
    </Suspense>
  );
}
