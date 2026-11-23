"use client";

import { RotateCw, ShieldAlert, WifiOff, type LucideIcon } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { ApiError, ApiErrorKind } from "@/lib/api";

const TITLES: Record<ApiErrorKind, string> = {
  unauthorized: "Sessão não encontrada",
  not_found: "Item não encontrado",
  conflict: "Alteração bloqueada",
  validation: "Revise os dados informados",
  unavailable: "Assistente indisponível",
  network: "Sem conexão com o Vezo",
  unknown: "Algo deu errado",
};

const ICONS: Partial<Record<ApiErrorKind, LucideIcon>> = {
  network: WifiOff,
  unavailable: WifiOff,
};

interface ErrorStateProps {
  error: ApiError;
  onRetry?: () => void;
  className?: string;
}

/**
 * Alerta gracioso para falhas da API. Mostra a mensagem já sanitizada pelo cliente
 * (`ApiError.message`) e, quando faz sentido, um botão de nova tentativa.
 */
export function ErrorState({ error, onRetry, className }: ErrorStateProps) {
  const Icon = ICONS[error.kind] ?? ShieldAlert;
  const canRetry =
    onRetry && (error.kind === "network" || error.kind === "unavailable" || error.kind === "unknown");

  return (
    <Alert variant="destructive" className={className}>
      <Icon aria-hidden />
      <AlertTitle>{TITLES[error.kind]}</AlertTitle>
      <AlertDescription>
        <p>{error.message}</p>
        {error.fieldErrors.length > 1 ? (
          <ul className="mt-1 list-disc pl-4">
            {error.fieldErrors.map((item) => (
              <li key={`${item.field}-${item.message}`}>
                {item.field ? <strong>{item.field}: </strong> : null}
                {item.message}
              </li>
            ))}
          </ul>
        ) : null}
        {canRetry ? (
          <Button variant="outline" className="mt-3" onClick={onRetry}>
            <RotateCw aria-hidden />
            Tentar novamente
          </Button>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}
