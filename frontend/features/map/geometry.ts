/** Escalas e geometrias do mapa (BR-050, BR-051). Funções puras. */

export interface RainClass {
  id: string;
  label: string;
  min: number;
  color: string;
}

/** Faixas visuais de chuva prevista em 24 h — não são alertas (BR-050). */
export const RAIN_CLASSES: readonly RainClass[] = [
  { id: "sem", label: "Sem chuva (0 mm)", min: 0, color: "#c9d6df" },
  { id: "fraca", label: "Fraca (até 5 mm)", min: 0.05, color: "#7fb3c9" },
  { id: "moderada", label: "Moderada (5–25 mm)", min: 5, color: "#3a86b4" },
  { id: "forte", label: "Forte (25–50 mm)", min: 25, color: "#1d4f91" },
  { id: "muito-forte", label: "Muito forte (acima de 50 mm)", min: 50, color: "#5b2a86" },
];

export function rainClass(mm: number): RainClass {
  let current = RAIN_CLASSES[0]!;
  for (const c of RAIN_CLASSES) if (mm >= c.min) current = c;
  return current;
}

export const COLUMN_BASE_M = 150;
export const COLUMN_M_PER_MM = 60;
export const COLUMN_MAX_M = 4000;

/** Altura da coluna 3D (BR-051): linear, com teto. */
export function columnHeight(mm: number): number {
  return Math.min(COLUMN_BASE_M + Math.max(mm, 0) * COLUMN_M_PER_MM, COLUMN_MAX_M);
}

/** Polígono aproximando um círculo de raio `radiusM` metros (anel fechado, [lon, lat]). */
export function circlePolygon(lon: number, lat: number, radiusM: number, steps = 32): number[][] {
  const earth = 6_371_008.8;
  const dLat = (radiusM / earth) * (180 / Math.PI);
  const dLon = dLat / Math.cos((lat * Math.PI) / 180);
  const ring: number[][] = [];
  for (let i = 0; i < steps; i++) {
    const a = (2 * Math.PI * i) / steps;
    ring.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)]);
  }
  ring.push(ring[0]!);
  return ring;
}

export const STATION_STATUS: Record<string, { label: string; color: string }> = {
  OPERATIONAL: { label: "Operante", color: "#1e7a46" },
  FAULT: { label: "Em pane", color: "#b42318" },
  INACTIVE: { label: "Desativada", color: "#5b6670" },
  UNKNOWN: { label: "Situação desconhecida", color: "#5b6670" },
};
