"use client";

import { useState, type FormEvent } from "react";
import { validateLocation, type SavedLocation } from "@/features/locations/store";

interface LocationPickerProps {
  locations: SavedLocation[];
  defaultId: string;
  selected: { lat: number; lon: number; name: string };
  persisted: boolean;
  onSelect: (location: SavedLocation) => void;
  onAdd: (location: Omit<SavedLocation, "id">) => void;
  onRemove: (id: string) => void;
  onSetDefault: (id: string) => void;
}

const inputClass =
  "w-full rounded-md border border-surface-border px-2 py-1.5 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent";
const buttonClass =
  "rounded-md border border-accent px-3 py-1.5 text-sm font-medium text-accent hover:bg-accent hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-60";

/** Seleção, inclusão e remoção de locais salvos neste navegador (FR-045, ADR-008). */
export function LocationPicker(props: LocationPickerProps) {
  const { locations, defaultId, selected, persisted, onSelect, onAdd, onRemove, onSetDefault } =
    props;
  const [name, setName] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [geoMessage, setGeoMessage] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);

  const selectedId =
    locations.find((l) => l.lat === selected.lat && l.lon === selected.lon)?.id ?? "";

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const latNum = Number(lat.replace(",", "."));
    const lonNum = Number(lon.replace(",", "."));
    const problem = validateLocation(name, latNum, lonNum);
    setError(problem);
    if (problem) return;
    onAdd({ name, lat: latNum, lon: lonNum });
    setName("");
    setLat("");
    setLon("");
  }

  function useMyLocation() {
    if (!("geolocation" in navigator)) {
      setGeoMessage("Este navegador não oferece geolocalização.");
      return;
    }
    setLocating(true);
    setGeoMessage(null);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        setLat(position.coords.latitude.toFixed(5));
        setLon(position.coords.longitude.toFixed(5));
        if (!name) setName("Minha localização");
        setGeoMessage("Coordenadas preenchidas. Confira o nome e clique em Salvar local.");
      },
      () => {
        setLocating(false);
        setGeoMessage("Não foi possível obter a localização (permissão negada ou indisponível).");
      },
      { timeout: 10_000, maximumAge: 300_000 },
    );
  }

  return (
    <section aria-labelledby="locais-titulo" className="space-y-3 rounded-lg border border-surface-border bg-surface p-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1">
          <label id="locais-titulo" htmlFor="local-select" className="block text-sm font-medium">
            Local
          </label>
          <select
            id="local-select"
            className={inputClass}
            value={selectedId}
            onChange={(e) => {
              const location = locations.find((l) => l.id === e.target.value);
              if (location) onSelect(location);
            }}
          >
            {selectedId === "" && <option value="">{selected.name} (da URL)</option>}
            {locations.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
                {l.id === defaultId ? " (padrão)" : ""}
              </option>
            ))}
          </select>
        </div>
        {selectedId && selectedId !== defaultId && (
          <button type="button" className={buttonClass} onClick={() => onSetDefault(selectedId)}>
            Definir como padrão
          </button>
        )}
        {selectedId && selectedId !== "centro-sp" && (
          <button type="button" className={buttonClass} onClick={() => onRemove(selectedId)}>
            Remover local
          </button>
        )}
      </div>

      <details>
        <summary className="cursor-pointer text-sm font-medium">Adicionar local</summary>
        <form onSubmit={submit} className="mt-3 grid gap-3 sm:grid-cols-4" noValidate>
          <div className="sm:col-span-2">
            <label htmlFor="local-nome" className="block text-xs text-ink-muted">Nome</label>
            <input id="local-nome" className={inputClass} value={name} onChange={(e) => setName(e.target.value)} maxLength={60} />
          </div>
          <div>
            <label htmlFor="local-lat" className="block text-xs text-ink-muted">Latitude</label>
            <input id="local-lat" inputMode="decimal" className={inputClass} value={lat} onChange={(e) => setLat(e.target.value)} placeholder="-23,5505" />
          </div>
          <div>
            <label htmlFor="local-lon" className="block text-xs text-ink-muted">Longitude</label>
            <input id="local-lon" inputMode="decimal" className={inputClass} value={lon} onChange={(e) => setLon(e.target.value)} placeholder="-46,6333" />
          </div>
          <div className="flex flex-wrap gap-2 sm:col-span-4">
            <button type="submit" className={buttonClass}>Salvar local</button>
            <button type="button" className={buttonClass} onClick={useMyLocation} disabled={locating}>
              {locating ? "Obtendo localização…" : "Usar minha localização"}
            </button>
          </div>
          {error && <p role="alert" className="text-sm text-status-error sm:col-span-4">{error}</p>}
          {geoMessage && <p role="status" className="text-sm text-ink-muted sm:col-span-4">{geoMessage}</p>}
        </form>
      </details>

      {!persisted && (
        <p role="status" className="text-xs text-status-warn">
          Este navegador não permitiu salvar os locais; eles valem só até fechar a página.
        </p>
      )}
      <p className="text-xs text-ink-muted">Os locais ficam salvos apenas neste navegador.</p>
    </section>
  );
}
