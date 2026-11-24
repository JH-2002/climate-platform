export type BasinSort = "alto" | "setores" | "ocorrencias" | "piscinoes" | "nome";

export interface DemStatus {
  available: boolean;
  resolution_m: number | null;
  created_at: string | null;
  sha256: string | null;
  bounds: Record<string, number> | null;
  attribution: string;
  disclaimer: string;
}

export interface BasinSummary {
  id: number;
  name: string;
  main_basin: string | null;
  area_km2: number | null;
  coverage: string | null;
  sectors: number;
  sectors_by_grade: Record<"R4" | "R3" | "R2" | "R1", number>;
  households: number | null;
  high_or_above_now: number;
  occurrences_12m: number;
  reservoirs: number;
  reservoir_volume_m3: number | null;
  elev_min_m: number | null;
  elev_median_m: number | null;
  elev_max_m: number | null;
}

export interface BasinList {
  items: BasinSummary[];
  total_sectors: number;
  sectors_outside_basins: number;
  risk_computed_at: string | null;
  occurrences_since: string;
  attribution: string;
  disclaimer: string;
}

export interface BasinSector {
  id: number;
  code: string;
  name: string | null;
  subprefecture: string | null;
  grade: number;
  households: number | null;
  category_now: string | null;
  elev_median_m: number | null;
  relative_elev_m: number | null;
  nearest_drainage_m: number | null;
}

export interface BasinReservoir {
  id: number;
  name: string;
  code: string | null;
  volume_m3: number | null;
  kind: string | null;
  stream: string | null;
  manager: string | null;
}

export interface BasinDetail {
  basin: BasinSummary;
  sectors: BasinSector[];
  reservoirs: BasinReservoir[];
  drainage_km_open: number;
  drainage_km_closed: number;
  occurrences_since: string;
  attribution: string;
  disclaimer: string;
}

export interface NearestDrainage {
  id: number;
  name: string | null;
  course_type: string;
  open_channel: boolean;
  distance_m: number;
}

export interface SectorTerrain {
  sector_id: number;
  computed_at: string;
  elev_median_m: number | null;
  elev_min_m: number | null;
  slope_mean_pct: number | null;
  relative_elev_m: number | null;
  cells: number;
  low_sample: boolean;
  basin_id: number | null;
  basin_name: string | null;
  main_basin: string | null;
  nearest_drainage: NearestDrainage | null;
  dem_resolution_m: number | null;
  attribution: string;
  hydro_attribution: string;
  disclaimer: string;
}

export interface ProfilePoint {
  distance_m: number;
  longitude: number;
  latitude: number;
  elevation_m: number | null;
}

export interface ProfileCrossing {
  kind: "drainage" | "sector";
  id: number;
  name: string | null;
  detail: string | null;
  distance_m: number;
  elevation_m: number | null;
}

export interface Profile {
  length_m: number;
  samples: ProfilePoint[];
  crossings: ProfileCrossing[];
  elevation_min_m: number | null;
  elevation_max_m: number | null;
  gain_m: number;
  loss_m: number;
  step_m: number;
  attribution: string;
  hydro_attribution: string;
  disclaimer: string;
}

export interface BasinLayerProps {
  id: number;
  name: string;
  main_basin: string | null;
  sectors: number;
  high_or_above_now: number;
  occurrences_12m: number;
  reservoirs: number;
}
