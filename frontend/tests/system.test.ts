import { describe, expect, it, vi } from "vitest";
import { fetchReadiness } from "@/features/system/api";
import type { ReadinessReport } from "@/features/system/types";
import { deriveReadinessViewState } from "@/features/system/view-state";
import { ApiError } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";

const report = (status: "ok" | "degraded"): ReadinessReport => ({
  status,
  checked_at: "2026-11-19T15:00:00Z",
  components: {
    db: { status: "ok", latency_ms: 2.1, detail: null, info: {} },
    redis: {
      status: status === "ok" ? "ok" : "unavailable",
      latency_ms: null,
      detail: status === "ok" ? null : "sem resposta em 2 s",
      info: {},
    },
  },
});

function jsonResponse(body: unknown, status: number, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

describe("deriveReadinessViewState", () => {
  const base = { isPending: false, isError: false, data: undefined, online: true };

  it("sem conexão tem prioridade sobre tudo", () => {
    expect(deriveReadinessViewState({ ...base, online: false, data: report("ok") })).toBe("offline");
  });
  it("carregando enquanto a primeira requisição está pendente", () => {
    expect(deriveReadinessViewState({ ...base, isPending: true })).toBe("loading");
  });
  it("erro quando a requisição falhou e não há dados", () => {
    expect(deriveReadinessViewState({ ...base, isError: true })).toBe("error");
  });
  it("sucesso / degradado seguem o relatório", () => {
    expect(deriveReadinessViewState({ ...base, data: report("ok") })).toBe("success");
    expect(deriveReadinessViewState({ ...base, data: report("degraded") })).toBe("degraded");
  });
});

describe("fetchReadiness", () => {
  it("trata 503 com relatório como dado (degradado), não como erro", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(report("degraded"), 503));
    const result = await fetchReadiness(undefined, fetchImpl);
    expect(result.status).toBe("degraded");
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/health/ready",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("converte Problem Details em ApiError com correlation ID", async () => {
    const problem = {
      type: "about:blank",
      title: "Recurso não encontrado",
      status: 404,
      correlation_id: "abc",
    };
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse(problem, 404, { "X-Correlation-ID": "abc" }));
    const error = await fetchReadiness(undefined, fetchImpl).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).correlationId).toBe("abc");
    expect((error as ApiError).message).toBe("Recurso não encontrado");
  });

  it("informa falhas de rede com mensagem legível", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const error = await fetchReadiness(undefined, fetchImpl).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBeNull();
    expect((error as ApiError).message).toBe("Não foi possível conectar à API.");
  });
});

describe("formatDateTime", () => {
  it("converte UTC para o horário de São Paulo", () => {
    expect(formatDateTime("2026-11-19T15:00:00Z")).toBe("19/11/2026, 12:00:00");
  });
  it("lida com entrada inválida", () => {
    expect(formatDateTime("nope")).toBe("data inválida");
  });
});
