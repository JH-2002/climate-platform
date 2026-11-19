/** Espelha `ForecastResponse` de `app/api/v1/weather.py`. Tudo aqui é previsão de modelo. */
import type { Freshness, FreshnessReason } from "@/features/sources/types";

export interface HourlyValues {
  valid_at: string;
  air_temperature: number | null;
  precipitation: number | null;
  relative_humidity: number | null;
  wind_speed: number | null;
}

export interface DailyValues {
  date: string;
  air_temperature_max: number | null;
  air_temperature_min: number | null;
  precipitation_sum: number | null;
  precipitation_probability_max: number | null;
}

export interface PrecipitationOutlook {
  hours: number;
  total_mm: number;
  complete: boolean;
  hours_available: number;
}

export interface ForecastResponse {
  kind: "FORECAST";
  point: { latitude: number; longitude: number; distance_km: number };
  source: {
    code: string;
    name: string;
    attribution: string;
    freshness: Freshness;
    reason: FreshnessReason;
    last_success_at: string | null;
  };
  issued_at: string;
  now: HourlyValues | null;
  hourly: HourlyValues[];
  daily: DailyValues[];
  precipitation_outlook: PrecipitationOutlook[];
  units: Record<string, string>;
}
