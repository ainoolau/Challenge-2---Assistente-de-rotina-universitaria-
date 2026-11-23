"use client";

import { RotateCw, WifiOff } from "lucide-react";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useApiHealth } from "@/hooks/use-api-health";
import { useOnlineStatus } from "@/hooks/use-online-status";

/**
 * Faixa global de conectividade:
 * - offline no navegador → aviso âmbar (dados podem estar desatualizados);
 * - API fora do ar / 503 → alerta com "Tentar novamente".
 * Não renderiza nada quando está tudo saudável.
 */
export function ConnectionBanner() {
  const online = useOnlineStatus();
  // Revalida /health sempre que a conexão volta.
  const { state, recheck } = useApiHealth(online);

  if (!online) {
    return (
      <Alert variant="warning" className="rounded-none border-x-0 border-t-0">
        <WifiOff aria-hidden />
        <AlertTitle>Você está offline</AlertTitle>
        <AlertDescription>
          Suas alterações não serão enviadas até a conexão voltar.
        </AlertDescription>
      </Alert>
    );
  }

  if (state.status !== "down") return null;

  return (
    <Alert variant="destructive" className="rounded-none border-x-0 border-t-0 pr-36">
      <WifiOff aria-hidden />
      <AlertTitle>Vezo indisponível no momento</AlertTitle>
      <AlertDescription>
        {state.error.kind === "network"
          ? "Não conseguimos falar com o servidor. Algumas informações podem não carregar."
          : state.error.message}
      </AlertDescription>
      <AlertAction className="top-1/2 -translate-y-1/2">
        <Button variant="outline" size="sm" onClick={() => void recheck()}>
          <RotateCw aria-hidden />
          Tentar de novo
        </Button>
      </AlertAction>
    </Alert>
  );
}
