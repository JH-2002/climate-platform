/**
 * Cliente HTTP tipado e mínimo para a API da plataforma.
 * Interpreta Problem Details (RFC 9457) e guarda o correlation ID para suporte.
 */

export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
  correlation_id?: string | null;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
    readonly correlationId: string | null,
    readonly problem: ProblemDetails | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface ApiResponse<T> {
  data: T;
  status: number;
  correlationId: string | null;
}

export function apiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/+$/, "");
}

function isProblem(value: unknown): value is ProblemDetails {
  return (
    typeof value === "object" &&
    value !== null &&
    "status" in value &&
    "title" in value &&
    typeof (value as { status: unknown }).status === "number"
  );
}

export interface GetOptions {
  signal?: AbortSignal;
  /** Status fora da faixa 2xx cujo corpo é um payload válido (ex.: readiness 503). */
  acceptStatuses?: readonly number[];
  fetchImpl?: typeof fetch;
}

export async function apiGet<T>(path: string, options: GetOptions = {}): Promise<ApiResponse<T>> {
  const { signal, acceptStatuses = [], fetchImpl = fetch } = options;
  let response: Response;
  try {
    response = await fetchImpl(`${apiBaseUrl()}${path}`, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("Não foi possível conectar à API.", null, null);
  }

  const correlationId = response.headers.get("X-Correlation-ID");
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (response.ok || acceptStatuses.includes(response.status)) {
    if (body === null) {
      throw new ApiError("Resposta da API sem conteúdo válido.", response.status, correlationId);
    }
    return { data: body as T, status: response.status, correlationId };
  }

  const problem = isProblem(body) ? body : null;
  throw new ApiError(
    problem?.detail ?? problem?.title ?? `Erro HTTP ${response.status}`,
    response.status,
    correlationId ?? problem?.correlation_id ?? null,
    problem,
  );
}
