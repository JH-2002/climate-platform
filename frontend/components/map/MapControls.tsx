import { ALL_LAYERS, LAYER_LABELS, type LayerId, type MapMode } from "@/features/map/state";

interface MapControlsProps {
  mode: MapMode;
  layers: LayerId[];
  webgl: boolean;
  onModeChange: (mode: MapMode) => void;
  onToggleLayer: (id: LayerId) => void;
}

const modeButton =
  "rounded-md border px-3 py-1.5 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

export function MapControls({ mode, layers, webgl, onModeChange, onToggleLayer }: MapControlsProps) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-lg border border-surface-border bg-surface p-3">
      <div role="group" aria-label="Modo do mapa" className="flex gap-2">
        {(["2d", "3d"] as const).map((m) => (
          <button
            key={m}
            type="button"
            aria-pressed={mode === m}
            disabled={!webgl}
            onClick={() => onModeChange(m)}
            className={`${modeButton} ${
              mode === m ? "border-accent bg-accent text-white" : "border-surface-border text-ink hover:bg-surface-muted"
            } disabled:opacity-50`}
          >
            {m === "3d" ? "3D com relevo" : "2D plano"}
          </button>
        ))}
      </div>
      <fieldset className="flex flex-wrap gap-x-4 gap-y-2">
        <legend className="sr-only">Camadas</legend>
        {ALL_LAYERS.map((id) => (
          <label key={id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={layers.includes(id)}
              onChange={() => onToggleLayer(id)}
              className="h-4 w-4 accent-[#0b5c7a]"
            />
            {LAYER_LABELS[id]}
          </label>
        ))}
      </fieldset>
    </div>
  );
}
