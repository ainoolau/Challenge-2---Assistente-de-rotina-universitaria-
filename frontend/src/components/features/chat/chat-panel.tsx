"use client";

import { MessageSquareText } from "lucide-react";
import Link from "next/link";

import { useSession } from "@/components/providers/session-provider";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { PageSkeleton } from "@/components/states/loading-state";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Painel do Chat Assistente (casca). A conversa, citações, abstenção segura e
 * card de proposta são implementados na #49 sobre `api.chat.*`.
 */
export function ChatPanel({ className }: { className?: string }) {
  const { state, refresh } = useSession();

  return (
    <section aria-labelledby="chat-titulo" className={cn("flex flex-col gap-4", className)}>
      <header className="flex flex-col gap-1">
        <h2 id="chat-titulo" className="text-xl font-semibold">
          Assistente Vezo
        </h2>
        <p className="text-sm text-muted-foreground">
          Respostas com fontes citadas. Nenhuma mudança na agenda sem sua confirmação.
        </p>
      </header>

      {state.status === "loading" ? <PageSkeleton label="Carregando conversa…" /> : null}
      {state.status === "error" ? (
        <ErrorState error={state.error} onRetry={() => void refresh()} />
      ) : null}
      {state.status === "anonymous" ? (
        <EmptyState
          icon={MessageSquareText}
          title="Configure sua rotina primeiro"
          description="O assistente usa sua agenda e preferências de sono para sugerir horários."
          action={
            <Button asChild>
              <Link href="/onboarding">Configurar rotina</Link>
            </Button>
          }
        />
      ) : null}
      {state.status === "authenticated" ? (
        <EmptyState
          icon={MessageSquareText}
          title="Nenhuma conversa ainda"
          description="Pergunte sobre editais, prazos ou peça para encaixar horas de estudo na sua semana."
        />
      ) : null}
    </section>
  );
}
