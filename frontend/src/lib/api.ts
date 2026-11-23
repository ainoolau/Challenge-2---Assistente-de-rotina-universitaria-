/**
 * Cliente HTTP tipado para a API FastAPI do Vezo (`src/api/main.py`).
 *
 * - Autenticação: cookie HttpOnly `vezo_session` emitido por `POST /sessions`.
 *   Por isso TODA requisição usa `credentials: "include"`. O token nunca é lido
 *   nem guardado pelo JavaScript (nada de localStorage).
 * - Base URL: `NEXT_PUBLIC_API_URL` (padrão `http://localhost:8000`). Para usar o
 *   proxy same-origin do Next (`/api/*`, ver next.config.ts), defina
 *   `NEXT_PUBLIC_API_URL=/api` e `API_PROXY_TARGET` com a URL real da API.
 * - Erros: toda falha vira `ApiError` com `kind` estável e mensagem em português.
 */

import type {
  ApiErrorBody,
  ChatHistoryMessage,
  ChatQueryRequest,
  ChatQueryResponse,
  DocumentItem,
  DocumentUploadResponse,
  HealthResponse,
  OptimizeScheduleRequest,
  PreferencesUpdateRequest,
  ProposalActionResponse,
  ReallocateScheduleRequest,
  ScheduleItemCreate,
  ScheduleItemResponse,
  ScheduleItemUpdate,
  ScheduleListQuery,
  ScheduleListResponse,
  ScheduleProposalResponse,
  SessionCreateRequest,
  SessionPreferences,
  SessionResponse,
  ValidationErrorItem,
} from "@/types/api";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

// ---------------------------------------------------------------------------
// Erros estruturados
// ---------------------------------------------------------------------------

export type ApiErrorKind =
  | "unauthorized" // 401 — sessão ausente/expirada: levar ao onboarding
  | "not_found" // 404
  | "conflict" // 409 — sono protegido, item fixo ou proposta defasada
  | "validation" // 422 — erro de campo (Pydantic)
  | "unavailable" // 503 — Qdrant/Groq/ingestão indisponível
  | "network" // sem conexão / API fora do ar / CORS
  | "unknown";

export interface FieldError {
  /** Caminho do campo, ex.: "sleep_end" ou "study_goals.0.deadline". */
  field: string;
  message: string;
}

const DEFAULT_MESSAGES: Record<ApiErrorKind, string> = {
  unauthorized: "Sua sessão expirou ou ainda não foi criada. Configure sua rotina para continuar.",
  not_found: "Não encontramos este item na sua sessão.",
  conflict: "Esta alteração entra em conflito com regras protegidas da sua agenda.",
  validation: "Alguns campos estão inválidos. Revise e tente novamente.",
  unavailable: "O assistente está temporariamente indisponível. Tente novamente em instantes.",
  network: "Não foi possível conectar ao Vezo. Verifique sua conexão.",
  unknown: "Algo deu errado. Tente novamente.",
};

export class ApiError extends Error {
  readonly status: number;
  readonly kind: ApiErrorKind;
  readonly fieldErrors: FieldError[];

  constructor(
    status: number,
    kind: ApiErrorKind,
    message: string,
    fieldErrors: FieldError[] = [],
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
    this.fieldErrors = fieldErrors;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

function kindFromStatus(status: number): ApiErrorKind {
  if (status === 401) return "unauthorized";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 422 || status === 400 || status === 413) return "validation";
  if (status === 502 || status === 503 || status === 504) return "unavailable";
  return "unknown";
}

function toFieldErrors(items: ValidationErrorItem[]): FieldError[] {
  return items.map((item) => ({
    // Remove prefixos de localização do FastAPI ("body", "query").
    field: item.loc
      .filter((part) => part !== "body" && part !== "query")
      .join("."),
    message: item.msg.replace(/^Value error, /, ""),
  }));
}

async function toApiError(response: Response): Promise<ApiError> {
  const kind = kindFromStatus(response.status);
  let body: Partial<ApiErrorBody> | null = null;
  try {
    body = (await response.json()) as Partial<ApiErrorBody>;
  } catch {
    // Corpo vazio ou não-JSON (ex.: proxy reverso): usa mensagem padrão.
  }

  const detail = body?.detail;
  if (Array.isArray(detail)) {
    const fieldErrors = toFieldErrors(detail);
    return new ApiError(
      response.status,
      kind,
      fieldErrors[0]?.message ?? DEFAULT_MESSAGES[kind],
      fieldErrors,
    );
  }
  // 409/404/400 trazem mensagens de domínio já em português, seguras para exibir.
  // 5xx são sanitizados pelo backend; ainda assim preferimos a mensagem padrão.
  const message =
    typeof detail === "string" && detail && response.status < 500
      ? detail
      : DEFAULT_MESSAGES[kind];
  return new ApiError(response.status, kind, message);
}

// ---------------------------------------------------------------------------
// Núcleo de requisição
// ---------------------------------------------------------------------------

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface RequestOptions {
  method?: HttpMethod;
  /** Objeto serializado como JSON, ou FormData para upload. */
  body?: unknown;
  query?: Record<string, string | undefined>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = `${API_BASE_URL}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) params.set(key, value);
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

export async function apiRequest<T>(
  path: string,
  { method = "GET", body, query, signal }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body; // o navegador define o boundary do multipart
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: payload,
      signal,
      credentials: "include", // obrigatório para o cookie HttpOnly vezo_session
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "network", DEFAULT_MESSAGES.network);
  }

  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// Endpoints (contrato oficial — docs/ARCHITECTURE.md §5.2)
// ---------------------------------------------------------------------------

const enc = encodeURIComponent;

export const api = {
  health: (signal?: AbortSignal) =>
    apiRequest<HealthResponse>("/health", { signal }),

  sessions: {
    create: (body: SessionCreateRequest = {}) =>
      apiRequest<SessionResponse>("/sessions", { method: "POST", body }),
    me: (signal?: AbortSignal) =>
      apiRequest<SessionResponse>("/sessions/me", { signal }),
  },

  preferences: {
    get: (signal?: AbortSignal) =>
      apiRequest<SessionPreferences>("/preferences", { signal }),
    replace: (body: PreferencesUpdateRequest) =>
      apiRequest<SessionPreferences>("/preferences", { method: "PUT", body }),
    update: (body: PreferencesUpdateRequest) =>
      apiRequest<SessionPreferences>("/preferences", { method: "PATCH", body }),
  },

  schedule: {
    list: (horizon?: ScheduleListQuery, signal?: AbortSignal) =>
      apiRequest<ScheduleListResponse>("/schedule", {
        query: horizon ? { ...horizon } : undefined,
        signal,
      }),
    create: (body: ScheduleItemCreate) =>
      apiRequest<ScheduleItemResponse>("/schedule", { method: "POST", body }),
    update: (
      itemId: string,
      body: ScheduleItemUpdate,
      options?: { forceFixed?: boolean },
    ) =>
      apiRequest<ScheduleItemResponse>(`/schedule/${enc(itemId)}`, {
        method: "PATCH",
        body,
        query: options?.forceFixed ? { force_fixed: "true" } : undefined,
      }),
    remove: (itemId: string, options?: { forceFixed?: boolean }) =>
      apiRequest<void>(`/schedule/${enc(itemId)}`, {
        method: "DELETE",
        query: options?.forceFixed ? { force_fixed: "true" } : undefined,
      }),
    optimize: (body: OptimizeScheduleRequest) =>
      apiRequest<ScheduleProposalResponse>("/schedule/optimize", {
        method: "POST",
        body,
      }),
    reallocate: (body: ReallocateScheduleRequest) =>
      apiRequest<ScheduleProposalResponse>("/schedule/reallocate", {
        method: "POST",
        body,
      }),
    /** Só chamar após clique explícito do usuário em "Confirmar e aplicar". */
    confirmProposal: (proposalId: string) =>
      apiRequest<ProposalActionResponse>(
        `/schedule/proposals/${enc(proposalId)}/confirm`,
        { method: "POST" },
      ),
    rejectProposal: (proposalId: string) =>
      apiRequest<ProposalActionResponse>(
        `/schedule/proposals/${enc(proposalId)}/reject`,
        { method: "POST" },
      ),
  },

  documents: {
    list: (signal?: AbortSignal) =>
      apiRequest<DocumentItem[]>("/documents", { signal }),
    upload: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return apiRequest<DocumentUploadResponse>("/documents/upload", {
        method: "POST",
        body: form,
      });
    },
  },

  chat: {
    query: (body: ChatQueryRequest, signal?: AbortSignal) =>
      apiRequest<ChatQueryResponse>("/chat/query", {
        method: "POST",
        body,
        signal,
      }),
    history: (signal?: AbortSignal) =>
      apiRequest<ChatHistoryMessage[]>("/chat/history", { signal }),
  },
} as const;
