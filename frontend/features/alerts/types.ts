/** Tipos da API de alertas (spec 009). Oficiais e do sistema nunca se misturam (BR-140). */

import type { MultiPolygon } from "geojson";

export type OfficialCategory = "CIVIL_DEFENSE" | "WEATHER_WARNING";
export type SystemCategory = "RISK_ESTIMATE" | "DATA_QUALITY";
export type AlertCategory = OfficialCategory | SystemCategory;
export type OfficialStatus = "UPCOMING" | "ACTIVE" | "EXPIRED" | "CANCELLED" | "SUPERSEDED";
export type Freshness = "FRESH" | "DELAYED" | "STALE" | "UNAVAILABLE" | "UNKNOWN";

export interface OfficialAlert {
  id: number;
  category: OfficialCategory;
  category_label: string;
  source_code: string;
  attribution: string;
  sender_name: string | null;
  msg_type: string;
  event: string | null;
  severity: string | null;
  severity_label: string;
  level_name: string | null;
  color: string | null;
  urgency: string | null;
  certainty: string | null;
  headline: string | null;
  description: string | null;
  instruction: string | null;
  web: string | null;
  area_desc: string | null;
  sent_at: string;
  onset_at: string | null;
  expires_at: string | null;
  ended_at: string | null;
  status: OfficialStatus;
  subprefectures: string[];
  city_fraction: number | null;
  area_approximate: boolean;
}

export interface OfficialAlertDetail extends OfficialAlert {
  geometry: MultiPolygon | null;
  references: string[];
}

export interface SystemAlert {
  id: number;
  rule_code: string;
  rules_version: string;
  category: SystemCategory;
  category_label: string;
  level: "HIGH" | "CRITICAL" | "WARNING" | string;
  scope_label: string;
  title: string;
  message: string;
  details: Record<string, unknown>;
  opened_at: string;
  updated_at: string;
  closed_at: string | null;
  status: "OPEN" | "CLOSED";
}

export interface AlertSource {
  code: string;
  name: string;
  attribution: string;
  freshness: Freshness;
  last_success_at: string | null;
}

export interface ActiveAlerts {
  generated_at: string;
  official: OfficialAlert[];
  system: SystemAlert[];
  counts: Record<string, number>;
  sources: AlertSource[];
  sources_ok: boolean;
  cge_url: string;
  official_channel: string;
}

export interface HistoryEntry {
  kind: "official" | "system";
  id: number;
  category: AlertCategory;
  category_label: string;
  title: string;
  level: string | null;
  level_label: string;
  start_at: string | null;
  end_at: string | null;
  status: string;
}

export interface AlertHistory {
  items: HistoryEntry[];
  total: number;
  page: number;
  page_size: number;
  since: string;
  until: string;
}

export interface AlertLayerProps {
  id: number;
  category: OfficialCategory;
  category_label: string;
  severity: string | null;
  severity_label: string;
  headline: string | null;
  status: OfficialStatus;
  kind: "OFFICIAL";
}
