/**
 * Cliente HTTP tipado e mínimo para a API da plataforma.
 * Interpreta Problem Details (RFC 9457) e guarda o correlation ID para suporte.
 * No modo demonstração (spec 012) lê as respostas gravadas em vez de chamar a API.
 */
import { DEMO_MESSAGES, demoEnabled, demoFallbackFile, demoFile, demoUrl, demoWriteMessage } from "@/lib/demo";

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

/** Vazio = mesma origem (o Next encaminha /api/* para o backend). */
export function apiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/+$/, "");
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
  return request<T>("GET", path, undefined, options);
}

/** POST com corpo JSON; erros chegam como `ApiError` com o `detail` da API. */
export async function apiPost<T>(path: string, body: unknown, options: GetOptions = {}): Promise<ApiResponse<T>> {
  return request<T>("POST", path, body, options);
}

async function request<T>(
  method: "GET" | "POST",
  path: string,
  payload: unknown,
  options: GetOptions,
): Promise<ApiResponse<T>> {
  if (demoEnabled()) return demoRequest<T>(method, path, payload, options);
  const { signal, acceptStatuses = [], fetchImpl = fetch } = options;
  let response: Response;
  try {
    response = await fetchImpl(`${apiBaseUrl()}${path}`, {
      method,
      headers:
        method === "POST"
          ? { Accept: "application/json", "Content-Type": "application/json" }
          : { Accept: "application/json" },
      body: method === "POST" ? JSON.stringify(payload) : undefined,
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

/** Uma resposta gravada, ou null se o arquivo não existe na vitrine. */
async function readRecorded(file: string, options: GetOptions): Promise<unknown> {
  const { signal, fetchImpl = fetch } = options;
  let response: Response;
  try {
    response = await fetchImpl(demoUrl(file), { signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("Não foi possível carregar os dados da demonstração.", null, null);
  }
  if (!response.ok) return null;
  try {
    return (await response.json()) as unknown;
  } catch {
    return null;
  }
}

async function demoRequest<T>(
  method: "GET" | "POST",
  path: string,
  payload: unknown,
  options: GetOptions,
): Promise<ApiResponse<T>> {
  const file = demoFile(method, path, payload);
  const candidates = method === "GET" ? [file, demoFallbackFile(path)] : [file];
  for (const candidate of candidates) {
    if (!candidate) continue;
    const data = await readRecorded(candidate, options);
    if (data !== null) return { data: data as T, status: 200, correlationId: null };
  }
  const message = method === "POST" ? demoWriteMessage(path) : DEMO_MESSAGES.unavailable;
  throw new ApiError(message, method === "POST" ? 422 : 404, null);
}
