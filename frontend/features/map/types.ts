/** GeoJSON das rotas `/api/v1/map/*` (RFC 7946). */

export interface PointGeometry {
  type: "Point";
  coordinates: [number, number];
}

export interface Feature<P, G = PointGeometry> {
  type: "Feature";
  id?: number;
  geometry: G;
  properties: P;
}

export interface FeatureCollection<P> {
  type: "FeatureCollection";
  features: Feature<P>[];
  attribution?: string;
}

export interface StationProps {
  id: number;
  code: string;
  name: string;
  status: string;
  source: string;
  altitude_m: number | null;
}

export interface ForecastPointProps {
  point_key: string;
  kind: "FORECAST";
  issued_at: string;
  valid_from: string;
  air_temperature_now: number | null;
  precipitation_24h: number;
  precipitation_24h_complete: boolean;
  precipitation_24h_hours: number;
}

export interface RegionFeature {
  type: "Feature";
  geometry: { type: "Polygon"; coordinates: number[][][] };
  properties: { name: string; kind: "REGION" };
}
