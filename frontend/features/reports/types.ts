/** Tipos da API de relatórios (spec 010). */

export type ReportType = "situacao" | "risco" | "alertas" | "chuva" | "simulacao";
export type ReportFormat = "pdf" | "csv" | "json";
export type ReportStatus = "QUEUED" | "RUNNING" | "DONE" | "FAILED" | "EXPIRED";

export interface ParamInfo {
  name: string;
  label: string;
  required: boolean;
  help: string;
}

export interface ReportTypeInfo {
  code: ReportType;
  title: string;
  description: string;
  formats: ReportFormat[];
  params: ParamInfo[];
}

export interface ReportRequest {
  id: string;
  report_type: ReportType;
  format: ReportFormat;
  title: string;
  params: Record<string, unknown>;
  mode: "REAL" | "SIMULATION";
  status: ReportStatus;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  expires_at: string | null;
  bytes: number | null;
  filename: string | null;
  download_url: string | null;
}

export interface ReportForm {
  type: ReportType;
  format: ReportFormat;
  subprefecture: string;
  since: string;
  until: string;
  category: string;
  point: string;
  grain: "day" | "month" | "year";
  simulationId: string;
}
