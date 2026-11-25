"use client";

import type { FormEvent } from "react";
import { titleCase } from "@/features/risk/categories";
import type { ReportForm as Form, ReportFormat, ReportType, ReportTypeInfo } from "@/features/reports/types";

const FORMAT_LABELS: Record<ReportFormat, string> = {
  pdf: "PDF (para ler e imprimir)",
  csv: "CSV (planilha)",
  json: "JSON (outros sistemas)",
};

const CATEGORY_OPTIONS = [
  { value: "", label: "Todas" },
  { value: "CIVIL_DEFENSE", label: "Alertas da Defesa Civil" },
  { value: "WEATHER_WARNING", label: "Avisos do INMET" },
  { value: "RISK_ESTIMATE", label: "Estimativa do sistema" },
  { value: "DATA_QUALITY", label: "Qualidade dos dados" },
];

const FIELD = "rounded-md border border-surface-border bg-surface px-2 py-1.5 text-sm";

interface Props {
  types: ReportTypeInfo[];
  form: Form;
  subprefectures: string[];
  points: { key: string; label: string }[];
  pending: boolean;
  error: string | null;
  onChange: (form: Form) => void;
  onSubmit: () => void;
}

/** Tipo, formato e os parâmetros que cada tipo aceita (FR-156). */
export function ReportForm({ types, form, subprefectures, points, pending, error, onChange, onSubmit }: Props) {
  const info = types.find((t) => t.code === form.type) ?? types[0];
  const set = <K extends keyof Form>(key: K, value: Form[K]) => onChange({ ...form, [key]: value });

  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <form onSubmit={submit} className="space-y-4 rounded-lg border border-surface-border bg-surface p-4" aria-labelledby="novo-relatorio">
      <h2 id="novo-relatorio" className="text-lg font-semibold">
        Novo relatório
      </h2>
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Relatório</legend>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {types.map((t) => (
            <label
              key={t.code}
              className={`flex cursor-pointer gap-2 rounded-md border p-3 text-sm ${
                form.type === t.code ? "border-accent bg-accent/5" : "border-surface-border"
              }`}
            >
              <input type="radio" name="tipo" value={t.code} checked={form.type === t.code} onChange={() => set("type", t.code as ReportType)} />
              <span>
                <span className="block font-medium">{t.title}</span>
                <span className="block text-ink-muted">{t.description}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      {info && info.params.length > 0 && (
        <fieldset className="flex flex-wrap items-end gap-4 text-sm">
          <legend className="mb-1 font-medium">Parâmetros</legend>
          {form.type === "risco" && (
            <label className="flex flex-col gap-1">
              Subprefeitura
              <select aria-label="Subprefeitura" className={FIELD} value={form.subprefecture} onChange={(e) => set("subprefecture", e.target.value)}>
                <option value="">Cidade inteira</option>
                {subprefectures.map((s) => (
                  <option key={s} value={s}>
                    {titleCase(s)}
                  </option>
                ))}
              </select>
            </label>
          )}
          {(form.type === "alertas" || form.type === "chuva") && (
            <>
              <label className="flex flex-col gap-1">
                Desde
                <input type="date" required aria-label="Desde" className={FIELD} value={form.since} onChange={(e) => set("since", e.target.value)} />
              </label>
              <label className="flex flex-col gap-1">
                Até
                <input type="date" required aria-label="Até" className={FIELD} value={form.until} onChange={(e) => set("until", e.target.value)} />
              </label>
            </>
          )}
          {form.type === "alertas" && (
            <label className="flex flex-col gap-1">
              Categoria
              <select aria-label="Categoria" className={FIELD} value={form.category} onChange={(e) => set("category", e.target.value)}>
                {CATEGORY_OPTIONS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          {form.type === "chuva" && (
            <>
              <label className="flex flex-col gap-1">
                Ponto
                <select aria-label="Ponto" className={FIELD} value={form.point} onChange={(e) => set("point", e.target.value)}>
                  <option value="">Centro (padrão)</option>
                  {points.map((p) => (
                    <option key={p.key} value={p.key}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1">
                Agregação
                <select aria-label="Agregação" className={FIELD} value={form.grain} onChange={(e) => set("grain", e.target.value as Form["grain"])}>
                  <option value="day">Por dia (até 3 anos)</option>
                  <option value="month">Por mês</option>
                  <option value="year">Por ano</option>
                </select>
              </label>
            </>
          )}
          {form.type === "simulacao" && (
            <label className="flex flex-col gap-1">
              Id da simulação
              <input
                required
                aria-label="Id da simulação"
                className={`${FIELD} w-80 font-mono`}
                value={form.simulationId}
                onChange={(e) => set("simulationId", e.target.value.trim())}
                placeholder="Copie do link do Laboratório"
              />
            </label>
          )}
        </fieldset>
      )}

      <fieldset className="flex flex-wrap gap-4 text-sm">
        <legend className="mb-1 font-medium">Formato</legend>
        {(info?.formats ?? ["pdf", "csv", "json"]).map((f) => (
          <label key={f} className="flex items-center gap-2">
            <input type="radio" name="formato" value={f} checked={form.format === f} onChange={() => set("format", f)} />
            {FORMAT_LABELS[f]}
          </label>
        ))}
      </fieldset>

      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={pending} className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-60">
          {pending ? "Enviando…" : "Gerar relatório"}
        </button>
        <span className="text-xs text-ink-muted">A geração roda em segundo plano; o arquivo fica disponível por 7 dias.</span>
      </div>
      {error && (
        <p role="alert" className="text-sm text-status-error">
          {error}
        </p>
      )}
    </form>
  );
}
