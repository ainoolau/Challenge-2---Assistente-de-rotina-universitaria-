"use client";

import { CalendarDays, CalendarPlus } from "lucide-react";
import Link from "next/link";
import { useSyncExternalStore } from "react";

import { ChatPanel } from "@/components/features/chat/chat-panel";
import { useSession } from "@/components/providers/session-provider";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { ScheduleSkeleton } from "@/components/states/loading-state";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const VIEWS = [
  { value: "hoje", label: "Hoje" },
  { value: "semana", label: "Semana" },
  { value: "mes", label: "Mês" },
] as const;

/**
 * Dashboard de Rotina (casca). Desktop: Rotina (~62%) + Chat (~38%) lado a lado.
 * Mobile: apenas a Rotina; o chat fica na aba "Assistente".
 * Timeline, prioridades e conflitos são implementados na #48 sobre `api.schedule.*`.
 */
export function DashboardView() {
  return (
    <div className="grid flex-1 gap-6 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,38%)] lg:gap-0 lg:p-0">
      <RoutinePanel />
      <aside
        aria-label="Assistente"
        className="hidden border-l bg-card lg:block lg:px-6 lg:py-8"
      >
        <div className="sticky top-24">
          <ChatPanel />
        </div>
      </aside>
    </div>
  );
}

function RoutinePanel() {
  const { state, refresh } = useSession();
  const today = useToday();

  return (
    <section aria-labelledby="rotina-titulo" className="flex flex-col gap-5 lg:px-8 lg:py-8">
      <header className="flex flex-col gap-1">
        <h1 id="rotina-titulo" className="text-2xl font-semibold lg:text-3xl">
          Sua rotina
        </h1>
        <p className="min-h-5 text-sm text-muted-foreground first-letter:uppercase">{today}</p>
      </header>

      {state.status === "loading" ? <ScheduleSkeleton /> : null}

      {state.status === "error" ? (
        <ErrorState error={state.error} onRetry={() => void refresh()} />
      ) : null}

      {state.status === "anonymous" ? (
        <EmptyState
          icon={CalendarPlus}
          title="Vamos montar sua rotina"
          description="Informe aulas, trabalho e seu horário de sono. O Vezo protege seu descanso e sugere blocos de estudo."
          action={
            <Button asChild size="lg">
              <Link href="/onboarding">Configurar rotina</Link>
            </Button>
          }
        />
      ) : null}

      {state.status === "authenticated" ? (
        <Tabs defaultValue="hoje" className="gap-4">
          <TabsList aria-label="Período da agenda">
            {VIEWS.map((view) => (
              <TabsTrigger key={view.value} value={view.value} className="px-4">
                {view.label}
              </TabsTrigger>
            ))}
          </TabsList>
          {VIEWS.map((view) => (
            <TabsContent key={view.value} value={view.value}>
              <EmptyState
                icon={CalendarDays}
                title="Agenda vazia"
                description="Seus compromissos fixos, sono protegido e blocos de estudo aparecerão aqui."
              />
            </TabsContent>
          ))}
        </Tabs>
      ) : null}
    </section>
  );
}

const noopSubscribe = () => () => {};
const formatToday = () =>
  new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "numeric", month: "long" }).format(
    new Date(),
  );

/** Data de hoje no fuso do navegador; vazio no prerender (evita divergência de hidratação). */
function useToday(): string {
  return useSyncExternalStore(noopSubscribe, formatToday, () => "");
}
