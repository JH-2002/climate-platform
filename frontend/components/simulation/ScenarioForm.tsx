"use client";

import { titleCase } from "@/features/risk/categories";
import type { SavedLocation } from "@/features/locations/store";
import {
  DEFAULT_CENTER,
  DEFAULT_OPTIONS,
  LIMITS,
  PATTERN_LABELS,
  peakHourMm,
  usesStorm,
  validateScenario,
} from "@/features/simulation/scenario";
import type { Center, Pattern, Preset, RunOptions, ScenarioInput } from "@/features/simulation/types";
import { formatNumber } from "@/lib/format";

interface Props {
  scenario: ScenarioInput;
  options?: RunOptions;
  preset: string | null;
  presets: Preset[];
  centers: Center[];
  locations: SavedLocation[];
  pending: boolean;
  error: string | null;
  onChange: (scenario: ScenarioInput, preset: string | null) => void;
  onOptionsChange?: (options: RunOptions) => void;
  onSubmit: () => void;
}

const field = "rounded-md border border-surface-border bg-surface px-2 py-1.5";

function toNumber(raw: string): number {
  return raw.trim() === "" ? Number.NaN : Number(raw.replace(",", "."));
}

function shown(value: number): string {
  return Number.isFinite(value) ? String(value) : "";
}

function NumberField(props: {
  id: string;
  label: string;
  unit: string;
  value: number;
  limits: readonly [number, number];
  step?: number;
  error?: string;
  hint?: string;
  placeholder?: string;
  onChange: (value: number) => void;
}) {
  const { id, label, unit, value, limits, step = 1, error, hint, placeholder, onChange } = props;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs text-ink-muted">
        {label}
        {unit && ` (${unit})`}
      </label>
      <input
        id={id}
        type="number"
        inputMode="decimal"
        min={limits[0]}
        max={limits[1]}
        step={step}
        className={field}
        value={shown(value)}
        placeholder={placeholder}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-erro` : hint ? `${id}-dica` : undefined}
        onChange={(e) => onChange(toNumber(e.target.value))}
      />
      {error && (
        <p id={`${id}-erro`} className="text-xs text-red-800">
          {error}
        </p>
      )}
      {!error && hint && (
        <p id={`${id}-dica`} className="text-xs text-ink-muted">
          {hint}
        </p>
      )}
    </div>
  );
}

/** Formulário do cenário (FR-100, FR-103). Funciona sem o mapa (NFR-103). */
export function ScenarioForm(props: Props) {
  const { scenario, preset, presets, centers, locations, pending, error, onChange, onSubmit } = props;
  const options = props.options ?? DEFAULT_OPTIONS;
  const errors = validateScenario(scenario, options);
  const invalid = Object.keys(errors).length > 0;
  const set = (patch: Partial<ScenarioInput>) => onChange({ ...scenario, ...patch }, null);
  const setOptions = (patch: Partial<RunOptions>) => props.onOptionsChange?.({ ...options, ...patch });
  const hybrid = options.mode === "HYBRID";
  const storm = usesStorm(options);
  const selectedPreset = presets.find((p) => p.code === preset) ?? null;

  function chooseCenter(value: string) {
    const [kind, ...rest] = value.split(":");
    const key = rest.join(":");
    const cell = scenario.cell ?? { ...DEFAULT_CENTER, radius_km: 6 };
    if (kind === "sub") {
      const c = centers.find((x) => x.name === key);
      if (c) set({ cell: { ...cell, latitude: c.latitude, longitude: c.longitude } });
    } else if (kind === "local") {
      const l = locations.find((x) => x.id === key);
      if (l) set({ cell: { ...cell, latitude: l.lat, longitude: l.lon } });
    } else if (kind === "se") {
      set({ cell: { ...cell, ...DEFAULT_CENTER } });
    }
  }

  return (
    <form
      className="space-y-4 rounded-lg border border-surface-border bg-surface p-4"
      aria-labelledby="cenario-titulo"
      onSubmit={(e) => {
        e.preventDefault();
        if (!invalid) onSubmit();
      }}
    >
      <h2 id="cenario-titulo" className="text-lg font-semibold">
        Cenário de chuva
      </h2>

      {props.onOptionsChange && (
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Ponto de partida</legend>
          <div className="flex flex-col gap-1 text-sm">
            <label className="flex items-center gap-2">
              <input type="radio" name="sim-modo" checked={!hybrid} onChange={() => setOptions({ mode: "SIMULATION" })} />
              Só o cenário (chuva toda escolhida por você)
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" name="sim-modo" checked={hybrid} onChange={() => setOptions({ mode: "HYBRID" })} />
              A partir da previsão real das próximas 24 h
            </label>
          </div>
          {hybrid && (
            <div className="space-y-2 rounded-md bg-surface-muted p-2">
              <NumberField
                id="sim-multiplicador"
                label="Chuva prevista multiplicada por"
                unit="%"
                value={Math.round(options.multiplier * 100)}
                limits={LIMITS.multiplier_pct}
                step={10}
                error={errors.multiplier}
                hint="100% = a previsão como está; 200% = o dobro."
                onChange={(pct) => setOptions({ multiplier: pct / 100 })}
              />
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={options.add_storm} onChange={(e) => setOptions({ add_storm: e.target.checked })} />
                Somar uma chuva do cenário (abaixo) à previsão
              </label>
              <p className="text-xs text-ink-muted">
                A chuva das 72 h anteriores é a real. Somar a hora mais forte do cenário à da previsão é o caso mais
                desfavorável.
              </p>
            </div>
          )}
        </fieldset>
      )}

      {storm && (
      <>
      {!hybrid && (
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Cenários prontos</legend>
        <div className="flex flex-wrap gap-2">
          {presets.map((p) => (
            <button
              key={p.code}
              type="button"
              aria-pressed={p.code === preset}
              onClick={() => onChange({ ...p.scenario, cell: p.scenario.cell ? { ...p.scenario.cell } : null }, p.code)}
              className={`rounded-full border px-3 py-1 text-sm ${p.code === preset ? "border-violet-700 bg-violet-700 text-white" : "border-surface-border hover:border-violet-700"}`}
            >
              {p.name}
            </button>
          ))}
        </div>
        {selectedPreset && (
          <div className="rounded-md bg-surface-muted p-2 text-sm">
            <p>{selectedPreset.description}</p>
            <p className="text-xs text-ink-muted">Origem do número: {selectedPreset.origin}</p>
          </div>
        )}
      </fieldset>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <NumberField
          id="sim-total"
          label="Chuva total"
          unit="mm"
          value={scenario.total_mm}
          limits={LIMITS.total_mm}
          error={errors.total}
          onChange={(total_mm) => set({ total_mm })}
        />
        <NumberField
          id="sim-duracao"
          label="Duração"
          unit="h"
          value={scenario.duration_h}
          limits={LIMITS.duration_h}
          error={errors.duration}
          onChange={(duration_h) => set({ duration_h })}
        />
        <div className="flex flex-col gap-1">
          <label htmlFor="sim-padrao" className="text-xs text-ink-muted">
            Distribuição no tempo
          </label>
          <select
            id="sim-padrao"
            className={field}
            value={scenario.pattern}
            onChange={(e) => set({ pattern: e.target.value as Pattern })}
          >
            {(Object.keys(PATTERN_LABELS) as Pattern[]).map((p) => (
              <option key={p} value={p}>
                {PATTERN_LABELS[p]}
              </option>
            ))}
          </select>
        </div>
        {!hybrid && (
          <NumberField
            id="sim-antecedente"
            label="Chuva das 72 h anteriores"
            unit="mm"
            value={scenario.antecedent_mm}
            limits={LIMITS.antecedent_mm}
            error={errors.antecedent}
            onChange={(antecedent_mm) => set({ antecedent_mm })}
          />
        )}
      </div>
      {!invalid && (
        <p className="text-xs text-ink-muted">
          Hora mais forte: {formatNumber(peakHourMm(scenario))} mm.
          {!hybrid && " A chuva das 72 h anteriores descreve o solo na cidade inteira."}
        </p>
      )}

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Área atingida</legend>
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input type="radio" name="sim-area" checked={scenario.cell === null} onChange={() => set({ cell: null })} />
            Cidade inteira
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="sim-area"
              checked={scenario.cell !== null}
              onChange={() => set({ cell: { ...DEFAULT_CENTER, radius_km: 6 } })}
            />
            Célula de chuva
          </label>
        </div>
        {scenario.cell && (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1">
              <label htmlFor="sim-centro" className="text-xs text-ink-muted">
                Centro da célula
              </label>
              <select id="sim-centro" className={field} value="" onChange={(e) => chooseCenter(e.target.value)}>
                <option value="">
                  Posição atual ({formatNumber(scenario.cell.latitude, 3)}; {formatNumber(scenario.cell.longitude, 3)})
                </option>
                <option value="se:">Centro (Praça da Sé)</option>
                {locations.length > 0 && (
                  <optgroup label="Meus locais">
                    {locations.map((l) => (
                      <option key={l.id} value={`local:${l.id}`}>
                        {l.name}
                      </option>
                    ))}
                  </optgroup>
                )}
                <optgroup label="Subprefeituras">
                  {centers.map((c) => (
                    <option key={c.name} value={`sub:${c.name}`}>
                      {titleCase(c.name)}
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>
            <NumberField
              id="sim-raio"
              label="Raio"
              unit="km"
              value={scenario.cell.radius_km}
              limits={LIMITS.radius_km}
              error={errors.radius}
              onChange={(radius_km) => set({ cell: { ...scenario.cell!, radius_km } })}
            />
            <p className="text-xs text-ink-muted sm:col-span-2">
              Escolha na lista ou clique no mapa. 100% da chuva até o raio, caindo em linha reta até 0% em
              duas vezes o raio.
            </p>
          </div>
        )}
      </fieldset>

      </>
      )}

      {props.onOptionsChange && (
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Incerteza (opcional)</legend>
          <NumberField
            id="sim-variacoes"
            label="Número de variações"
            unit=""
            value={options.members}
            limits={LIMITS.members}
            error={errors.members}
            hint="1 = só o cenário central. Com mais, cada variação muda a intensidade e a posição da chuva."
            onChange={(members) => setOptions({ members })}
          />
          {options.members > 1 && (
            <div className="grid gap-3 sm:grid-cols-2">
              <NumberField
                id="sim-intensidade"
                label="Intensidade varia até ±"
                unit="%"
                value={options.intensity_pct}
                limits={LIMITS.intensity_pct}
                error={errors.intensity}
                onChange={(intensity_pct) => setOptions({ intensity_pct })}
              />
              {storm && scenario.cell && (
                <NumberField
                  id="sim-deslocamento"
                  label="Centro se desloca até"
                  unit="km"
                  value={options.shift_km}
                  limits={LIMITS.shift_km}
                  step={0.5}
                  error={errors.shift}
                  onChange={(shift_km) => setOptions({ shift_km })}
                />
              )}
              <NumberField
                id="sim-seed"
                label="Seed"
                unit=""
                value={options.seed ?? Number.NaN}
                limits={LIMITS.seed}
                error={errors.seed}
                placeholder="sorteado"
                hint="Mesmo seed, mesmo resultado. Em branco, o sistema sorteia e grava."
                onChange={(seed) => setOptions({ seed: Number.isFinite(seed) ? seed : null })}
              />
            </div>
          )}
        </fieldset>
      )}

      {error && (
        <p role="alert" className="rounded-md border border-red-300 bg-red-50 p-2 text-sm text-red-900">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending || invalid}
        className="rounded-md bg-violet-700 px-4 py-2 font-medium text-white hover:bg-violet-800 disabled:opacity-50"
      >
        {pending ? "Simulando…" : "Simular"}
      </button>
    </form>
  );
}
