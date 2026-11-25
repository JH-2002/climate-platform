import type { ActiveAlerts, OfficialAlert, SystemAlert } from "@/features/alerts/types";

export function official(overrides: Partial<OfficialAlert> = {}): OfficialAlert {
  return {
    id: 1,
    category: "CIVIL_DEFENSE",
    category_label: "Alerta oficial — Defesa Civil",
    source_code: "idap-alerts",
    attribution: "Fonte: Defesa Civil (IDAP/MIDR)",
    sender_name: "Defesa Civil Estadual De São Paulo",
    msg_type: "Alert",
    event: "CHUVAS INTENSAS",
    severity: "Moderate",
    severity_label: "Moderada",
    level_name: null,
    color: null,
    urgency: "Immediate",
    certainty: "Observed",
    headline: "Defesa Civil:16:15 - Chuva se espalhando pelas Zonas Oeste e Sul de Sao Paulo.",
    description: "16:15 - Chuva se espalhando pelas Zonas Oeste e Sul de São Paulo.",
    instruction: "Em caso de emergência, ligue 199 ou 193.",
    web: "https://www.gov.br/mdr/pt-br/assuntos/protecao-e-defesa-civil/saiba-como-agir",
    area_desc: "SÃO PAULO/SP",
    sent_at: "2026-11-24T19:19:13Z",
    onset_at: "2026-11-24T19:19:13Z",
    expires_at: "2026-11-25T02:30:00Z",
    ended_at: null,
    status: "ACTIVE",
    subprefectures: ["LAPA", "PINHEIROS", "SE"],
    city_fraction: 0.21,
    area_approximate: false,
    ...overrides,
  };
}

export const inmetWarning = official({
  id: 7,
  category: "WEATHER_WARNING",
  category_label: "Aviso meteorológico oficial — INMET",
  source_code: "inmet-warnings",
  attribution: "Fonte: INMET — Alert-AS",
  sender_name: "Instituto Nacional de Meteorologia",
  event: "Tempestade",
  severity: "Severe",
  severity_label: "Severa",
  level_name: "Laranja — Perigo",
  color: "#F96602",
  headline: "Aviso de Tempestade. Severidade Grau: Severe",
  status: "UPCOMING",
  onset_at: "2026-11-25T03:00:00Z",
  expires_at: "2026-11-26T02:59:00Z",
  subprefectures: Array.from({ length: 32 }, (_, i) => `SUB ${i}`),
  city_fraction: 1,
});

export const riskAlert: SystemAlert = {
  id: 3,
  rule_code: "risk-subprefecture",
  rules_version: "1",
  category: "RISK_ESTIMATE",
  category_label: "Estimativa do sistema — não é alerta oficial",
  level: "CRITICAL",
  scope_label: "Penha",
  title: "Estimativa do sistema: risco crítico em Penha",
  message: "1 setor em crítico na estimativa mais recente. Estimativa experimental, não é alerta oficial.",
  details: { high: 0, critical: 1 },
  opened_at: "2026-11-24T18:00:00Z",
  updated_at: "2026-11-24T18:00:00Z",
  closed_at: null,
  status: "OPEN",
};

export const qualityAlert: SystemAlert = {
  ...riskAlert,
  id: 4,
  rule_code: "source-unavailable",
  category: "DATA_QUALITY",
  category_label: "Qualidade dos dados",
  level: "WARNING",
  scope_label: "avisos do INMET",
  title: "Fonte atrasada: avisos do INMET",
  message: "A coleta de avisos do INMET está atrasada.",
};

export function activeAlerts(overrides: Partial<ActiveAlerts> = {}): ActiveAlerts {
  return {
    generated_at: "2026-11-24T20:00:00Z",
    official: [official(), inmetWarning],
    system: [riskAlert],
    counts: {
      official_active: 1,
      official_upcoming: 1,
      civil_defense_active: 1,
      weather_warning_active: 0,
      risk_estimate: 1,
      data_quality: 0,
    },
    sources: [
      {
        code: "idap-alerts",
        name: "Defesa Civil — alertas à população (IDAP)",
        attribution: "Fonte: Defesa Civil (IDAP/MIDR)",
        freshness: "FRESH",
        last_success_at: "2026-11-24T19:55:00Z",
      },
      {
        code: "inmet-warnings",
        name: "INMET — avisos meteorológicos (Alert-AS)",
        attribution: "Fonte: INMET — Alert-AS",
        freshness: "FRESH",
        last_success_at: "2026-11-24T19:40:00Z",
      },
    ],
    sources_ok: true,
    cge_url: "https://www.cgesp.org",
    official_channel: "Para receber os alertas oficiais da Defesa Civil no celular, envie um SMS com o seu CEP para 40199.",
    ...overrides,
  };
}
