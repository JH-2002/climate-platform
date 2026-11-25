import Link from "next/link";
import { RiskBadge } from "@/components/risk/RiskBadge";
import { OCCURRENCE_TYPE_LABELS, titleCase } from "@/features/risk/categories";
import { riskHref } from "@/features/risk/state";
import type { OccurrenceProps, RiskArea } from "@/features/risk/types";
import type { FeatureCollection } from "@/features/map/types";

function formatDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-");
  return d && m && y ? `${d}/${m}/${y}` : isoDate;
}

interface WhereSectionProps {
  areas?: RiskArea[];
  occurrences?: FeatureCollection<OccurrenceProps>;
}

/** "Onde": setores com maior risco estimado e ocorrências mais recentes. */
export function WhereSection({ areas, occurrences }: WhereSectionProps) {
  const recent = (occurrences?.features ?? []).slice(0, 5);
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-2 rounded-lg border border-surface-border bg-surface p-4 text-sm">
        <h3 className="font-semibold">Setores com maior risco estimado</h3>
        {areas === undefined ? (
          <p className="text-ink-muted">Carregando…</p>
        ) : areas.length === 0 ? (
          <p className="text-ink-muted">Ainda não há estimativa de risco.</p>
        ) : (
          <ol className="space-y-1.5">
            {areas.map((area) => (
              <li key={area.id} className="flex flex-wrap items-center gap-2">
                <RiskBadge category={area.category} />
                <Link className="text-accent underline" href={riskHref(area.id)}>
                  {area.code}
                </Link>
                <span className="text-ink-muted">
                  {titleCase(area.name)} · {titleCase(area.subprefecture)}
                </span>
              </li>
            ))}
          </ol>
        )}
        <p className="text-xs text-ink-muted">Estimativa experimental do sistema — não é alerta oficial.</p>
      </div>
      <div className="space-y-2 rounded-lg border border-surface-border bg-surface p-4 text-sm">
        <h3 className="font-semibold">Ocorrências registradas mais recentes</h3>
        {occurrences === undefined ? (
          <p className="text-ink-muted">Carregando…</p>
        ) : recent.length === 0 ? (
          <p className="text-ink-muted">Nenhuma ocorrência nos últimos 12 meses.</p>
        ) : (
          <ul className="space-y-1">
            {recent.map((f, i) => (
              <li key={`${f.properties.occurred_on}-${i}`}>
                {OCCURRENCE_TYPE_LABELS[f.properties.type] ?? f.properties.type} em{" "}
                {formatDate(f.properties.occurred_on)} · {titleCase(f.properties.subprefecture)}
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-ink-muted">
          Fonte: GeoSampa (Defesa Civil/SIGRC); registros de atendimento, publicados com atraso.{" "}
          <Link className="text-accent underline" href="/map?modo=2d&camadas=ocorrencias,risco,regiao">
            Ver no mapa
          </Link>
        </p>
      </div>
    </div>
  );
}
