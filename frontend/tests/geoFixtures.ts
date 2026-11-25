import type { BasinBlock, BasinDetail, BasinList, Profile, SectorTerrain } from "@/features/geo/types";

const DISCLAIMER =
  "Relevo do Copernicus DEM GLO-30: modelo de superfície com ~30 m de resolução. Prédios e árvores entram na elevação. Serve para comparar bairros e bacias, não ruas. É contexto: não muda a categoria de risco.";

export function terrainFixture(sectorId: number, overrides: Partial<SectorTerrain> = {}): SectorTerrain {
  return {
    sector_id: sectorId,
    computed_at: "2026-11-24T15:00:00Z",
    elev_median_m: 731.4,
    elev_min_m: 728,
    slope_mean_pct: 6.2,
    relative_elev_m: -12.3,
    cells: 9,
    low_sample: false,
    basin_id: 9,
    basin_name: "Ribeirão Água Vermelha",
    main_basin: "Rio Tietê",
    nearest_drainage: { id: 7366, name: "Ribeirão Água Vermelha", course_type: "Trecho em estado natural", open_channel: true, distance_m: 84 },
    dem_resolution_m: 28.4,
    attribution: "Produced using Copernicus DEM GLO-30",
    hydro_attribution: "Bacias, drenagem e piscinões: GeoSampa — Prefeitura de São Paulo",
    disclaimer: DISCLAIMER,
    ...overrides,
  };
}

const basinA = {
  id: 252,
  name: "Rio Aricanduva",
  main_basin: "Rio Tietê",
  area_km2: 103.9,
  coverage: "Parcial",
  sectors: 41,
  sectors_by_grade: { R4: 3, R3: 12, R2: 14, R1: 12 },
  households: 5300,
  high_or_above_now: 4,
  occurrences_12m: 37,
  reservoirs: 9,
  reservoir_volume_m3: 1_250_000,
  elev_min_m: 722,
  elev_median_m: 768,
  elev_max_m: 890,
};

export const basinList: BasinList = {
  items: [
    basinA,
    {
      ...basinA,
      id: 9,
      name: "Ribeirão Água Vermelha",
      area_km2: 1.7,
      sectors: 3,
      sectors_by_grade: { R4: 0, R3: 1, R2: 1, R1: 1 },
      high_or_above_now: 0,
      occurrences_12m: 2,
      reservoirs: 0,
      reservoir_volume_m3: null,
    },
  ],
  total_sectors: 44,
  sectors_outside_basins: 1,
  risk_computed_at: "2026-11-24T15:00:00Z",
  occurrences_since: "2025-11-24",
  attribution: "Bacias, drenagem e piscinões: GeoSampa — Prefeitura de São Paulo",
  disclaimer: DISCLAIMER,
};

export const basinDetail: BasinDetail = {
  basin: basinA,
  sectors: [
    {
      id: 1,
      code: "HAF-06-02",
      name: "VILA FORMOSA",
      subprefecture: "ARICANDUVA-FORMOSA-CARRAO",
      grade: 4,
      households: 120,
      category_now: "HIGH",
      elev_median_m: 731,
      relative_elev_m: -14,
      nearest_drainage_m: 60,
    },
  ],
  reservoirs: [
    { id: 12, name: "Aricanduva V", code: "RAR-5", volume_m3: 167000, kind: "reservatorio off line", stream: "Aricanduva", manager: "Prefeitura" },
  ],
  drainage_km_open: 58.2,
  drainage_km_closed: 31.5,
  occurrences_since: "2025-11-24",
  attribution: "Bacias, drenagem e piscinões: GeoSampa — Prefeitura de São Paulo",
  disclaimer: DISCLAIMER,
};

export const profileFixture: Profile = {
  length_m: 90,
  samples: [
    { distance_m: 0, longitude: -46.55, latitude: -23.535, elevation_m: 740 },
    { distance_m: 30, longitude: -46.55, latitude: -23.5347, elevation_m: 731 },
    { distance_m: 60, longitude: -46.55, latitude: -23.5344, elevation_m: 724 },
    { distance_m: 90, longitude: -46.55, latitude: -23.5341, elevation_m: 733 },
  ],
  crossings: [
    { kind: "drainage", id: 905, name: "Rio Tietê", detail: "Trecho em estado natural", distance_m: 58, elevation_m: 724 },
    { kind: "sector", id: 4, name: "HMP-01-03", detail: "R3 · LOW", distance_m: 75, elevation_m: 728 },
  ],
  elevation_min_m: 724,
  elevation_max_m: 740,
  gain_m: 9,
  loss_m: 16,
  step_m: 30,
  attribution: "Produced using Copernicus DEM GLO-30",
  hydro_attribution: "GeoSampa",
  disclaimer: DISCLAIMER,
};

export const blockFixture: BasinBlock = {
  basin_id: 9,
  name: "Ribeirão Água Vermelha",
  main_basin: "Rio Tietê",
  bounds: { west: -46.44, south: -23.49, east: -46.418, north: -23.472 },
  elev_min_m: 722,
  elev_max_m: 768,
  source: "simulação",
  simulation_id: "4f9c2a8e-1b2d-4c3e-9f00-123456789abc",
  computed_at: "2026-11-24T18:00:00Z",
  banner: "SIMULAÇÃO — cenário hipotético, não é previsão nem alerta",
  sectors: [
    { id: 4, code: "HMP-01-03", name: "FAVELA DA PAZ", grade: 3, category: "CRITICAL", p_high: 0.9, longitude: -46.419, latitude: -23.4746 },
    { id: 5, code: "HMP-07-02", name: "JARDIM HELENA", grade: 2, category: "HIGH", p_high: 0.6, longitude: -46.431, latitude: -23.4768 },
    { id: 6, code: "HMP-07-01", name: "JARDIM HELENA", grade: 1, category: "LOW", p_high: 0, longitude: -46.43, latitude: -23.4756 },
  ],
  attribution: "Produced using Copernicus DEM GLO-30",
  hydro_attribution: "Bacias, drenagem e piscinões: GeoSampa — Prefeitura de São Paulo",
  disclaimer: DISCLAIMER,
};
