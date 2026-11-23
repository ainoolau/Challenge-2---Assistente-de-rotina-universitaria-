"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, api, isApiError } from "@/lib/api";
import type { HealthResponse } from "@/types/api";

export type ApiHealthState =
  | { status: "checking" }
  | { status: "ok"; health: HealthResponse }
  | { status: "down"; error: ApiError };

function toDown(error: unknown): ApiHealthState {
  return {
    status: "down",
    error: isApiError(error)
      ? error
      : new ApiError(0, "network", "Não foi possível conectar ao Vezo."),
  };
}

/**
 * Verifica `GET /health` ao montar e sempre que `recheckKey` mudar
 * (ex.: quando o navegador volta a ficar online).
 */
export function useApiHealth(recheckKey: unknown = null) {
  const [state, setState] = useState<ApiHealthState>({ status: "checking" });

  useEffect(() => {
    const controller = new AbortController();
    api
      .health(controller.signal)
      .then((health) => setState({ status: "ok", health }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setState(toDown(error));
      });
    return () => controller.abort();
  }, [recheckKey]);

  const recheck = useCallback(async () => {
    setState({ status: "checking" });
    try {
      setState({ status: "ok", health: await api.health() });
    } catch (error) {
      setState(toDown(error));
    }
  }, []);

  return { state, recheck };
}
