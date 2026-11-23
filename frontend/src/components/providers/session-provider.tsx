"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ApiError, api, isApiError } from "@/lib/api";
import type { SessionCreateRequest, SessionResponse } from "@/types/api";

/**
 * Estado global da sessão do PWA.
 *
 * A sessão vive no cookie HttpOnly `vezo_session` (inacessível ao JS); aqui apenas
 * consultamos `GET /sessions/me` para saber se ela existe e guardamos os dados públicos.
 */
export type SessionState =
  | { status: "loading" }
  | { status: "authenticated"; session: SessionResponse }
  | { status: "anonymous" }
  | { status: "error"; error: ApiError };

interface SessionContextValue {
  state: SessionState;
  /** Revalida a sessão no backend (ex.: após voltar a ficar online). */
  refresh: () => Promise<void>;
  /** Cria a sessão (POST /sessions) — o backend devolve o cookie HttpOnly. */
  createSession: (body?: SessionCreateRequest) => Promise<SessionResponse>;
}

const SessionContext = createContext<SessionContextValue | null>(null);

function toApiError(error: unknown): ApiError {
  return isApiError(error)
    ? error
    : new ApiError(0, "unknown", "Não foi possível verificar sua sessão.");
}

async function fetchSessionState(signal?: AbortSignal): Promise<SessionState> {
  try {
    const session = await api.sessions.me(signal);
    return { status: "authenticated", session };
  } catch (error) {
    if (isApiError(error) && error.kind === "unauthorized") {
      return { status: "anonymous" };
    }
    throw error;
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>({ status: "loading" });

  const refresh = useCallback(async () => {
    setState({ status: "loading" });
    try {
      setState(await fetchSessionState());
    } catch (error) {
      setState({ status: "error", error: toApiError(error) });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchSessionState(controller.signal)
      .then(setState)
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({ status: "error", error: toApiError(error) });
      });
    return () => controller.abort();
  }, []);

  const createSession = useCallback(async (body: SessionCreateRequest = {}) => {
    const session = await api.sessions.create(body);
    // O token também vem no corpo, mas é descartado: o cookie HttpOnly é a fonte.
    setState({ status: "authenticated", session: { ...session, session_token: null } });
    return session;
  }, []);

  const value = useMemo(
    () => ({ state, refresh, createSession }),
    [state, refresh, createSession],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession deve ser usado dentro de <SessionProvider>.");
  }
  return context;
}
