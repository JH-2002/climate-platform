/** Tipo de cada número (Constituição §7): sempre visível ao lado do valor. */

export const KIND_SHORT: Record<string, string> = {
  OBSERVED: "Medido",
  MODELED: "Modelo",
  FORECAST: "Previsão",
  DERIVED: "Calculado",
};

export function kindLabel(kind: string): string {
  return KIND_SHORT[kind] ?? kind;
}
