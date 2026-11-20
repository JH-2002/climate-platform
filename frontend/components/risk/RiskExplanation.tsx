import Link from "next/link";
import {
  FACTOR_EFFECT_LABELS,
  KIND_LABELS,
  OCCURRENCE_TYPE_LABELS,
  RAIN_LEVEL_LABELS,
  SUSCEPTIBILITY_LABELS,
  titleCase,
} from "@/features/risk/categories";
import type { RiskAreaDetail, RiskFactor } from "@/features/risk/types";
import { formatDateTime, formatNumber } from "@/lib/format";
import { RiskBadge } from "./RiskBadge";

const EFFECT_SYMBOL: Record<RiskFactor["effect"], string> = { raises: "↑", info: "i", unknown: "?" };

function weatherHref(detail: RiskAreaDetail): string {
  const params = new URLSearchParams({
    lat: detail.latitude.toFixed(4),
    lon: detail.longitude.toFixed(4),
    nome: `Setor ${detail.code}`,
  });
  return `/weather?${params}`;
}

function formatDate(isoDate: string | null): string {
  if (!isoDate) return "—";
  const [y, m, d] = isoDate.split("-");
  return `${d}/${m}/${y}`;
}

/** Por que o setor tem esta categoria (FR-067): fatores, entradas com tipo e fonte, histórico. */
export function RiskExplanation({ detail, onClose }: { detail: RiskAreaDetail; onClose: () => void }) {
  return (
    <section
      aria-labelledby="explicacao-titulo"
      className="space-y-4 rounded-lg border border-surface-border bg-surface p-4 text-sm"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 id="explicacao-titulo" className="text-lg font-semibold">
            Setor {detail.code} — {titleCase(detail.name)}
          </h2>
          <p className="text-ink-muted">
            {titleCase(detail.subprefecture)} · bacia {titleCase(detail.basin)} · vistoria em{" "}
            {formatDate(detail.inspected_on)}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-surface-border px-3 py-1.5 text-sm hover:bg-surface-muted"
        >
          Fechar explicação
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <RiskBadge category={detail.category} size="lg" />
        <span>
          {detail.rain_level === null ? "Sem estimativa de chuva" : RAIN_LEVEL_LABELS[detail.rain_level]} ×
          suscetibilidade {SUSCEPTIBILITY_LABELS[detail.susceptibility]?.toLowerCase()}
        </span>
      </div>

      <div>
        <h3 className="font-medium">Fatores</h3>
        <ul className="mt-1 space-y-1">
          {detail.factors.map((factor) => (
            <li key={factor.code} className="flex gap-2">
              <span
                aria-hidden="true"
                className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-surface-border text-xs font-semibold"
              >
                {EFFECT_SYMBOL[factor.effect]}
              </span>
              <span>
                {factor.text}
                <span className="sr-only"> ({FACTOR_EFFECT_LABELS[factor.effect]})</span>
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <caption className="py-1 text-left font-medium">Dados usados</caption>
          <thead className="text-ink-muted">
            <tr>
              <th scope="col" className="py-1 pr-4 font-medium">Dado</th>
              <th scope="col" className="py-1 pr-4 font-medium">Valor</th>
              <th scope="col" className="py-1 pr-4 font-medium">Tipo</th>
              <th scope="col" className="py-1 font-medium">Fonte</th>
            </tr>
          </thead>
          <tbody>
            {detail.inputs.map((input) => (
              <tr key={input.name} className="border-t border-surface-border">
                <th scope="row" className="py-1 pr-4 font-normal">{input.name}</th>
                <td className="py-1 pr-4 tabular-nums">
                  {input.value === null
                    ? "indisponível"
                    : input.unit === "grau"
                      ? `R${input.value}`
                      : `${formatNumber(input.value)} ${input.unit}`}
                </td>
                <td className="py-1 pr-4">{KIND_LABELS[input.kind] ?? input.kind}</td>
                <td className="py-1">{input.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {detail.forecast_distance_km !== null && (
          <p className="mt-1 text-xs text-ink-muted">
            Ponto de previsão a {formatNumber(detail.forecast_distance_km)} km do setor.
          </p>
        )}
      </div>

      <div>
        <h3 className="font-medium">
          Ocorrências registradas a até 300 m nos últimos 12 meses ({detail.nearby_occurrences.length})
        </h3>
        {detail.nearby_occurrences.length === 0 ? (
          <p className="text-ink-muted">Nenhuma ocorrência registrada no GeoSampa.</p>
        ) : (
          <ul className="mt-1 list-inside list-disc">
            {detail.nearby_occurrences.map((o, i) => (
              <li key={`${o.occurred_on}-${i}`}>
                {OCCURRENCE_TYPE_LABELS[o.type] ?? o.type} em {formatDate(o.occurred_on)} ·{" "}
                {formatNumber(o.distance_m, 0)} m
              </li>
            ))}
          </ul>
        )}
        <p className="mt-1 text-xs text-ink-muted">
          Registros de atendimento da Defesa Civil: podem não incluir todos os eventos.
        </p>
      </div>

      <p className="text-xs text-ink-muted">
        Estimativa {detail.run.id} calculada em {formatDateTime(detail.run.computed_at)} pelo motor{" "}
        <code>{detail.run.engine_version}</code>.
      </p>

      <div className="flex flex-wrap gap-4">
        <Link className="font-medium text-accent underline" href={weatherHref(detail)}>
          Ver previsão neste setor
        </Link>
        <a className="font-medium text-accent underline" href={detail.official_url} target="_blank" rel="noopener noreferrer">
          Abrir o GeoSampa (fonte oficial)
        </a>
      </div>
    </section>
  );
}
