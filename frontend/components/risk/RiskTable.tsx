import { RAIN_LEVEL_LABELS, SUSCEPTIBILITY_LABELS, titleCase } from "@/features/risk/categories";
import type { RiskArea } from "@/features/risk/types";
import { formatNumber } from "@/lib/format";
import { RiskBadge } from "./RiskBadge";

interface RiskTableProps {
  items: RiskArea[];
  total: number;
  selectedId: number | null;
  onSelect: (id: number) => void;
}

/** Ranking dos setores (FR-066): maior categoria primeiro, depois chuva e moradias. */
export function RiskTable({ items, total, selectedId, onSelect }: RiskTableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-surface-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" tabIndex={0} role="region" aria-label="Tabela de setores">
      <table className="w-full border-collapse bg-surface text-left text-sm">
        <caption className="bg-surface-muted px-4 py-2 text-left font-medium">
          Setores de risco hidrológico ({items.length < total ? `${items.length} de ${total}` : total})
        </caption>
        <thead className="text-ink-muted">
          <tr>
            <th scope="col" className="px-4 py-2 font-medium">Setor</th>
            <th scope="col" className="px-4 py-2 font-medium">Subprefeitura</th>
            <th scope="col" className="px-4 py-2 font-medium">Risco estimado</th>
            <th scope="col" className="px-4 py-2 font-medium">Chuva prevista</th>
            <th scope="col" className="px-4 py-2 font-medium">Suscetibilidade</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Moradias</th>
            <th scope="col" className="px-4 py-2 font-medium">
              <span className="sr-only">Ações</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((area) => (
            <tr
              key={area.id}
              className={`border-t border-surface-border ${selectedId === area.id ? "bg-surface-muted" : ""}`}
            >
              <th scope="row" className="px-4 py-2 font-medium">
                {area.code}
                <span className="block text-xs font-normal text-ink-muted">{titleCase(area.name)}</span>
              </th>
              <td className="px-4 py-2">{titleCase(area.subprefecture)}</td>
              <td className="px-4 py-2">
                <RiskBadge category={area.category} />
              </td>
              <td className="px-4 py-2">
                {area.rain_level === null ? (
                  "—"
                ) : (
                  <>
                    {RAIN_LEVEL_LABELS[area.rain_level]}
                    <span className="block text-xs text-ink-muted tabular-nums">
                      máx. {formatNumber(area.p1h_max_mm)} mm/h · {formatNumber(area.p24_mm)} mm em 24 h
                    </span>
                  </>
                )}
              </td>
              <td className="px-4 py-2">
                {SUSCEPTIBILITY_LABELS[area.susceptibility]} <span className="text-ink-muted">(R{area.grade})</span>
              </td>
              <td className="px-4 py-2 text-right tabular-nums">{area.households ?? "—"}</td>
              <td className="px-4 py-2">
                <button
                  type="button"
                  onClick={() => onSelect(area.id)}
                  aria-label={`Por quê? Explicação do setor ${area.code}`}
                  className="rounded-md border border-accent px-2 py-1 text-xs font-medium text-accent hover:bg-accent hover:text-white"
                >
                  Por quê?
                </button>
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={7} className="px-4 py-3 text-ink-muted">
                Nenhum setor com estes filtros.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
