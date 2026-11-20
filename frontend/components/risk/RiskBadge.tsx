import { CATEGORIES, type CategoryInfo } from "@/features/risk/categories";
import type { RiskCategory } from "@/features/risk/types";

function Shape({ shape, color }: { shape: CategoryInfo["shape"]; color: string }) {
  const common = { fill: color, stroke: "#ffffff", strokeWidth: 1 };
  return (
    <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" className="shrink-0">
      {shape === "circle" && <circle cx="7" cy="7" r="6" {...common} />}
      {shape === "triangle" && <polygon points="7,1 13,13 1,13" {...common} />}
      {shape === "diamond" && <polygon points="7,0.5 13.5,7 7,13.5 0.5,7" {...common} />}
      {shape === "octagon" && <polygon points="4,0.5 10,0.5 13.5,4 13.5,10 10,13.5 4,13.5 0.5,10 0.5,4" {...common} />}
      {shape === "question" && (
        <>
          <circle cx="7" cy="7" r="6" {...common} />
          <text x="7" y="10.5" textAnchor="middle" fontSize="9" fontWeight="700" fill="#ffffff">
            ?
          </text>
        </>
      )}
    </svg>
  );
}

/** Selo da categoria: forma + cor + texto (a categoria nunca depende só da cor). */
export function RiskBadge({ category, size = "sm" }: { category: RiskCategory; size?: "sm" | "lg" }) {
  const info = CATEGORIES[category];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${size === "lg" ? "px-3 py-1 text-base" : "px-2.5 py-0.5 text-sm"}`}
      style={{ backgroundColor: info.background, color: info.text, borderColor: info.color }}
    >
      <Shape shape={info.shape} color={info.color} />
      {info.label}
    </span>
  );
}

export function RiskSwatch({ category }: { category: RiskCategory }) {
  const info = CATEGORIES[category];
  return <Shape shape={info.shape} color={info.color} />;
}
