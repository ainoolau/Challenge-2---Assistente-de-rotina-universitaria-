"use client";

import {
  AlertTriangle,
  CalendarDays,
  CalendarPlus,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  MessageSquareText,
  Plus,
  RefreshCw,
  Shuffle,
  X,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { ChatPanel } from "@/components/features/chat/chat-panel";
import { useSession } from "@/components/providers/session-provider";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { ScheduleSkeleton } from "@/components/states/loading-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError, api, isApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  Interval,
  OptimizeScheduleRequest,
  ReallocateScheduleRequest,
  ScheduleItemResponse,
  ScheduleListResponse,
  ScheduleProposalResponse,
  StudyGoal,
} from "@/types/api";

import { GoalsPanel } from "./goals-panel";
import { ProposalReviewPanel } from "./proposal-review-panel";
import { ReallocateDialog } from "./reallocate-dialog";
import { ScheduleItemDialog, type ScheduleItemDraft } from "./schedule-item-dialog";
import {
  type RoutineViewMode,
  addDaysToKey,
  buildHorizonForDay,
  buildHorizonForWeek,
  classifyConflictError,
  durationMinutes,
  extractProposedBlocks,
  formatDayHeader,
  getDayLoad,
  getMonthGridKeys,
  getWeekKeys,
  groupByDateKey,
  isoToDateKey,
  itemHasConflict,
  toDateKey,
  toLocalTimeHHMM,
} from "./schedule-utils";
import {
  FreeWindowCard,
  ProposedSlotCard,
  ProtectedSleepCard,
  ScheduleSlotCard,
} from "./slot-card";

const VIEWS: readonly { value: RoutineViewMode; label: string }[] = [
  { value: "hoje", label: "Hoje" },
  { value: "semana", label: "Semana" },
  { value: "mes", label: "Mês" },
] as const;

const WEEKDAY_HEADERS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"] as const;

type LastProposalRequest =
  | { type: "optimize"; payload: OptimizeScheduleRequest }
  | { type: "reallocate"; payload: ReallocateScheduleRequest };

type BannerFeedback = {
  variant: "success" | "warning" | "destructive";
  title: string;
  description: string;
};

/**
 * Dashboard de Rotina (TASK-F1-05 / #48).
 * Desktop (>= 1024px): Rotina (~62%) + Chat (~38%) lado a lado.
 * Mobile (< 1024px): apenas a Rotina; o chat fica na aba "Assistente".
 */
export function DashboardView() {
  return (
    <div className="grid flex-1 grid-cols-1 gap-6 px-3.5 py-5 sm:px-4 sm:py-6 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,38%)] lg:gap-0 lg:p-0">
      <RoutinePanel />
      <aside
        aria-label="Assistente"
        className="hidden min-w-0 border-l bg-card lg:block lg:px-6 lg:py-8"
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
  const todayFormatted = useTodayLabel();

  return (
    <section
      aria-labelledby="rotina-titulo"
      className="flex min-w-0 flex-col gap-4 sm:gap-5 lg:px-8 lg:py-8"
    >
      <header className="flex flex-col gap-1">
        <h1 id="rotina-titulo" className="text-2xl font-semibold lg:text-3xl">
          Sua rotina
        </h1>
        <p className="min-h-5 text-sm text-muted-foreground first-letter:uppercase">
          {todayFormatted}
        </p>
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
        <AuthenticatedRoutine
          sessionTimezone={state.session.preferences.timezone}
          onSessionExpired={() => void refresh()}
        />
      ) : null}
    </section>
  );
}

function AuthenticatedRoutine({
  sessionTimezone,
  onSessionExpired,
}: {
  sessionTimezone: string;
  onSessionExpired: () => void;
}) {
  const todayKey = useTodayKey(sessionTimezone);

  const [viewMode, setViewMode] = useState<RoutineViewMode>("semana");
  const [selectedDateKey, setSelectedDateKey] = useState<string | null>(null);
  const anchorDateKey = selectedDateKey ?? todayKey;

  const [showFreeWindows, setShowFreeWindows] = useState(true);
  const [focusedWeekDay, setFocusedWeekDay] = useState<string | "all">("all");

  const [schedule, setSchedule] = useState<ScheduleListResponse | null>(null);
  const [loadingSchedule, setLoadingSchedule] = useState(true);
  const [scheduleError, setScheduleError] = useState<ApiError | null>(null);
  const [reloadTick, setReloadTick] = useState(0);

  // Metas de estudo & Proposta pendente
  const [goals, setGoals] = useState<StudyGoal[]>([]);
  const [optimizing, setOptimizing] = useState(false);
  const [optimizeError, setOptimizeError] = useState<string | null>(null);
  const [pendingProposal, setPendingProposal] = useState<ScheduleProposalResponse | null>(null);
  const [lastRequest, setLastRequest] = useState<LastProposalRequest | null>(null);
  const [proposalBusy, setProposalBusy] = useState<
    "confirm" | "reject" | "recalculate" | null
  >(null);
  const [proposalError, setProposalError] = useState<ApiError | null>(null);

  // Modais e feedback
  const [itemDialogOpen, setItemDialogOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<ScheduleItemResponse | null>(null);
  const [itemDraft, setItemDraft] = useState<ScheduleItemDraft>({
    dateKey: anchorDateKey,
    startTime: "09:00",
    endTime: "10:00",
  });
  const [reallocateOpen, setReallocateOpen] = useState(false);
  const [feedback, setFeedback] = useState<BannerFeedback | null>(null);

  const timeZone = schedule?.preferences.timezone ?? sessionTimezone;

  const weekKeys = useMemo(() => getWeekKeys(anchorDateKey), [anchorDateKey]);

  const activeHorizon = useMemo<Interval>(() => {
    if (viewMode === "hoje") {
      return buildHorizonForDay(anchorDateKey, timeZone);
    }
    return buildHorizonForWeek(weekKeys, timeZone);
  }, [viewMode, anchorDateKey, weekKeys, timeZone]);

  const weekHorizon = useMemo<Interval>(
    () => buildHorizonForWeek(weekKeys, timeZone),
    [weekKeys, timeZone],
  );

  // Carrega GET /schedule?horizon_start=...&horizon_end=...
  useEffect(() => {
    const controller = new AbortController();
    api.schedule
      .list(
        {
          horizon_start: activeHorizon.start,
          horizon_end: activeHorizon.end,
        },
        controller.signal,
      )
      .then((data) => {
        if (controller.signal.aborted) return;
        setSchedule(data);
        setScheduleError(null);
        setLoadingSchedule(false);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        if (isApiError(err) && err.kind === "unauthorized") {
          onSessionExpired();
          return;
        }
        setScheduleError(
          isApiError(err)
            ? err
            : new ApiError(0, "unknown", "Não foi possível carregar sua agenda."),
        );
        setLoadingSchedule(false);
      });

    return () => controller.abort();
  }, [activeHorizon.start, activeHorizon.end, reloadTick, onSessionExpired]);

  const triggerReload = useCallback(() => {
    setLoadingSchedule(true);
    setReloadTick((n) => n + 1);
  }, []);

  const goalsById = useMemo(
    () => Object.fromEntries(goals.map((g) => [g.goal_id, g])),
    [goals],
  );

  const proposedBlocks = useMemo(
    () =>
      pendingProposal
        ? extractProposedBlocks(
            pendingProposal.planning?.proposed_blocks,
            pendingProposal.rebalance?.proposed_blocks,
          )
        : [],
    [pendingProposal],
  );

  const itemsByDay = useMemo(
    () => groupByDateKey(schedule?.items ?? [], timeZone),
    [schedule?.items, timeZone],
  );

  const proposedByDay = useMemo(
    () => groupByDateKey(proposedBlocks, timeZone),
    [proposedBlocks, timeZone],
  );

  const freeWindowsByDay = useMemo(
    () => groupByDateKey(schedule?.free_windows ?? [], timeZone),
    [schedule?.free_windows, timeZone],
  );

  const goalDeadlinesByDay = useMemo(() => {
    const map: Record<string, StudyGoal[]> = {};
    for (const g of goals) {
      const k = isoToDateKey(g.deadline, timeZone);
      if (!map[k]) map[k] = [];
      map[k].push(g);
    }
    return map;
  }, [goals, timeZone]);

  function openCreateDialog(dateKey: string, startTime = "09:00", endTime = "10:00") {
    setEditingItem(null);
    setItemDraft({ dateKey, startTime, endTime, kind: "class", fixed: true });
    setItemDialogOpen(true);
  }

  function openCreateFromFreeWindow(win: Interval) {
    const dateKey = isoToDateKey(win.start, timeZone);
    const startTime = toLocalTimeHHMM(win.start, timeZone);
    const endTime = toLocalTimeHHMM(win.end, timeZone);
    openCreateDialog(dateKey, startTime, endTime);
  }

  function openEditDialog(item: ScheduleItemResponse) {
    setEditingItem(item);
    setItemDialogOpen(true);
  }

  async function handleOptimizeWeek() {
    if (goals.length === 0) return;
    setOptimizing(true);
    setOptimizeError(null);
    setProposalError(null);

    const request: OptimizeScheduleRequest = {
      horizon: weekHorizon,
      study_goals: goals,
    };

    try {
      const proposal = await api.schedule.optimize(request);
      setPendingProposal(proposal);
      setLastRequest({ type: "optimize", payload: request });
      setFeedback({
        variant: "warning",
        title: "Proposta gerada — aguardando sua confirmação",
        description:
          "Revise os blocos tracejados abaixo e clique em Confirmar e aplicar para gravá-los na agenda.",
      });
    } catch (err) {
      const apiErr = isApiError(err)
        ? err
        : new ApiError(0, "unknown", "Não foi possível otimizar a semana.");
      setOptimizeError(apiErr.message);
    } finally {
      setOptimizing(false);
    }
  }

  async function handleConfirmProposal() {
    if (!pendingProposal) return;
    setProposalBusy("confirm");
    setProposalError(null);

    try {
      const res = await api.schedule.confirmProposal(pendingProposal.proposal_id);
      setPendingProposal(null);
      setLastRequest(null);
      setFeedback({
        variant: "success",
        title: `Proposta aplicada (agenda v${res.schedule_version})`,
        description: res.message,
      });
      triggerReload();
    } catch (err) {
      const apiErr = isApiError(err)
        ? err
        : new ApiError(0, "unknown", "Não foi possível confirmar a proposta.");
      setProposalError(apiErr);
      if (apiErr.kind === "conflict" && classifyConflictError(apiErr.message) === "version") {
        // Recarrega a agenda para refletir a nova schedule_version e permitir recalcular.
        triggerReload();
      }
    } finally {
      setProposalBusy(null);
    }
  }

  async function handleRejectProposal() {
    if (!pendingProposal) return;
    setProposalBusy("reject");
    setProposalError(null);

    try {
      await api.schedule.rejectProposal(pendingProposal.proposal_id);
      setPendingProposal(null);
      setLastRequest(null);
      setFeedback({
        variant: "warning",
        title: "Proposta descartada",
        description: "Sua agenda confirmada permaneceu intacta.",
      });
    } catch (err) {
      const apiErr = isApiError(err)
        ? err
        : new ApiError(0, "unknown", "Não foi possível descartar a proposta.");
      setProposalError(apiErr);
    } finally {
      setProposalBusy(null);
    }
  }

  async function handleRecalculateProposal() {
    if (!lastRequest) return;
    setProposalBusy("recalculate");
    setProposalError(null);

    try {
      const next =
        lastRequest.type === "optimize"
          ? await api.schedule.optimize(lastRequest.payload)
          : await api.schedule.reallocate(lastRequest.payload);
      setPendingProposal(next);
      setFeedback({
        variant: "warning",
        title: `Proposta recalculada na versão v${next.base_version}`,
        description: "Revise os novos blocos tracejados antes de confirmar.",
      });
    } catch (err) {
      setProposalError(
        isApiError(err)
          ? err
          : new ApiError(0, "unknown", "Não foi possível recalcular a proposta."),
      );
    } finally {
      setProposalBusy(null);
    }
  }

  function shiftPeriod(direction: -1 | 1) {
    if (viewMode === "hoje") {
      setSelectedDateKey(addDaysToKey(anchorDateKey, direction));
    } else if (viewMode === "semana") {
      setSelectedDateKey(addDaysToKey(anchorDateKey, direction * 7));
      setFocusedWeekDay("all");
    } else {
      const [y, m] = anchorDateKey.split("-").map(Number);
      const next = new Date(Date.UTC(y ?? 2026, (m ?? 1) - 1 + direction, 15));
      setSelectedDateKey(
        `${next.getUTCFullYear()}-${String(next.getUTCMonth() + 1).padStart(2, "0")}-01`,
      );
    }
  }

  function jumpToToday() {
    setSelectedDateKey(todayKey);
    setFocusedWeekDay("all");
  }

  if (loadingSchedule && !schedule) {
    return <ScheduleSkeleton />;
  }

  if (scheduleError && !schedule) {
    return <ErrorState error={scheduleError} onRetry={triggerReload} />;
  }

  if (!schedule) return null;

  const conflicts = schedule.input_conflicts;
  const visibleWeekKeys =
    focusedWeekDay === "all" ? weekKeys : weekKeys.filter((k) => k === focusedWeekDay);
  const weekRangeLabel = `${formatDayHeader(weekKeys[0]).dayMonth} – ${formatDayHeader(weekKeys[6]).dayMonth}`;
  const monthGrid = getMonthGridKeys(anchorDateKey);

  return (
    <div className="flex min-w-0 flex-col gap-4 sm:gap-5">
      {/* Barra de ações rápidas + resumo da agenda */}
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="outline" className="font-mono">
            Agenda v{schedule.schedule_version}
          </Badge>
          <Badge variant="secondary" className="font-mono">
            {schedule.items.length} {schedule.items.length === 1 ? "item" : "itens"}
          </Badge>
          {schedule.free_windows.length > 0 ? (
            <Badge variant="outline">
              <Clock aria-hidden />
              {schedule.free_windows.length}{" "}
              {schedule.free_windows.length === 1 ? "janela livre" : "janelas livres"}
            </Badge>
          ) : null}
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={triggerReload}
            disabled={loadingSchedule}
            aria-label="Atualizar agenda"
            className="shrink-0"
          >
            <RefreshCw aria-hidden className={cn(loadingSchedule && "animate-spin")} />
            <span>Atualizar</span>
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={() => openCreateDialog(anchorDateKey)}
            className="flex-1 sm:flex-none"
          >
            <Plus aria-hidden />
            Novo compromisso
          </Button>
        </div>
      </div>

      {/* Feedback de ações */}
      {feedback ? (
        <Alert variant={feedback.variant}>
          {feedback.variant === "success" ? (
            <CheckCircle2 aria-hidden />
          ) : (
            <AlertTriangle aria-hidden />
          )}
          <AlertTitle>{feedback.title}</AlertTitle>
          <AlertDescription className="flex min-w-0 items-start justify-between gap-2">
            <span className="min-w-0 break-words">{feedback.description}</span>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              className="shrink-0"
              onClick={() => setFeedback(null)}
              aria-label="Fechar aviso"
            >
              <X aria-hidden />
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {/* Banner de erro ao recarregar mantendo dados anteriores visíveis */}
      {scheduleError ? <ErrorState error={scheduleError} onRetry={triggerReload} /> : null}

      {/* Banner acionável de conflitos pré-existentes (input_conflicts) */}
      {conflicts.length > 0 ? (
        <Alert variant="destructive">
          <AlertTriangle aria-hidden />
          <AlertTitle>
            {conflicts.length === 1
              ? "1 conflito entre compromissos fixos detectado"
              : `${conflicts.length} conflitos entre compromissos fixos detectados`}
          </AlertTitle>
          <AlertDescription className="flex min-w-0 flex-col gap-3">
            <p className="break-words">
              O Vezo <strong>nunca move compromissos fixos sozinho</strong>. Revise os horários
              sobrepostos abaixo, converse com o assistente ou rebalanceie seus blocos flexíveis:
            </p>
            <ul className="list-disc space-y-1 pl-4 text-xs">
              {conflicts.map((msg, idx) => (
                <li key={idx} className="break-words">
                  {msg}
                </li>
              ))}
            </ul>
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
              <Button asChild size="sm" variant="outline" className="w-full sm:w-auto">
                <Link href="/chat">
                  <MessageSquareText aria-hidden />
                  Resolver no Assistente
                </Link>
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="w-full sm:w-auto"
                onClick={() => setReallocateOpen(true)}
              >
                <Shuffle aria-hidden />
                Rebalancear blocos flexíveis
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      ) : null}

      {/* Card de revisão de proposta pendente (requires_confirmation=True) */}
      {pendingProposal ? (
        <ProposalReviewPanel
          proposal={pendingProposal}
          timeZone={timeZone}
          goalsById={goalsById}
          busyAction={proposalBusy}
          actionError={proposalError}
          onConfirm={() => void handleConfirmProposal()}
          onReject={() => void handleRejectProposal()}
          onRecalculate={lastRequest ? () => void handleRecalculateProposal() : undefined}
        />
      ) : null}

      {/* Abas Hoje / Semana / Mês */}
      <Tabs
        value={viewMode}
        onValueChange={(value) => setViewMode(value as RoutineViewMode)}
        className="min-w-0 gap-3.5"
      >
        <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between">
          <TabsList
            aria-label="Período da agenda"
            className="grid w-full grid-cols-3 sm:inline-flex sm:w-fit"
          >
            {VIEWS.map((view) => (
              <TabsTrigger key={view.value} value={view.value} className="px-3 sm:px-4">
                {view.label}
              </TabsTrigger>
            ))}
          </TabsList>

          <div className="flex items-center justify-between gap-2 sm:justify-end">
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              onClick={() => shiftPeriod(-1)}
              aria-label="Período anterior"
              className="shrink-0"
            >
              <ChevronLeft aria-hidden />
            </Button>

            <span className="min-w-0 flex-1 truncate text-center text-sm font-medium capitalize text-foreground sm:hidden">
              {viewMode === "semana"
                ? `Semana ${weekRangeLabel}`
                : viewMode === "mes"
                  ? monthGrid.monthLabel
                  : formatDayHeader(anchorDateKey).fullLabel}
            </span>

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={jumpToToday}
              className="hidden shrink-0 sm:inline-flex"
            >
              Hoje
            </Button>

            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              onClick={() => shiftPeriod(1)}
              aria-label="Próximo período"
              className="shrink-0"
            >
              <ChevronRight aria-hidden />
            </Button>
          </div>
        </div>

        {/* Subbarra: atalho Hoje (mobile) + período (desktop) + toggle de janelas livres */}
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={jumpToToday}
            className="shrink-0 sm:hidden"
          >
            Ir para hoje
          </Button>

          {viewMode !== "mes" ? (
            <span className="hidden font-medium capitalize text-foreground sm:inline">
              {viewMode === "semana"
                ? `Semana ${weekRangeLabel}`
                : formatDayHeader(anchorDateKey).fullLabel}
            </span>
          ) : (
            <span className="hidden sm:inline" />
          )}

          {viewMode !== "mes" ? (
            <label className="inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-lg border bg-card px-3 py-1 text-xs font-medium text-foreground select-none">
              <input
                type="checkbox"
                checked={showFreeWindows}
                onChange={(e) => setShowFreeWindows(e.target.checked)}
                className="size-4 accent-primary"
              />
              Janelas livres
            </label>
          ) : null}
        </div>

        {/* ==================== VISÃO SEMANA ==================== */}
        <TabsContent value="semana" className="flex min-w-0 flex-col gap-3.5">
          {/* Seletor semanal de 7 dias em grade fixa (sem rolagem horizontal em telas móveis) */}
          <div className="flex min-w-0 flex-col gap-2">
            <div className="flex items-center justify-between gap-2 text-xs">
              <span className="text-muted-foreground">
                {focusedWeekDay === "all"
                  ? "Mostrando a semana toda · toque em um dia para filtrar"
                  : `Filtrando ${formatDayHeader(focusedWeekDay).weekdayShort} · ${formatDayHeader(focusedWeekDay).dayMonth}`}
              </span>
              {focusedWeekDay !== "all" ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  className="shrink-0 text-primary"
                  onClick={() => setFocusedWeekDay("all")}
                >
                  Ver todos (7)
                </Button>
              ) : null}
            </div>

            <div
              className="grid grid-cols-7 gap-1 sm:gap-1.5"
              role="group"
              aria-label="Filtrar dia da semana"
            >
              {weekKeys.map((dayKey) => {
                const header = formatDayHeader(dayKey);
                const dayItems = itemsByDay[dayKey] ?? [];
                const dayProposed = proposedByDay[dayKey] ?? [];
                const count = dayItems.length + dayProposed.length;
                const hasDayConflict = dayItems.some((item) => itemHasConflict(item, conflicts));
                const isToday = dayKey === todayKey;
                const isSelected = focusedWeekDay === dayKey;

                return (
                  <button
                    key={dayKey}
                    type="button"
                    aria-pressed={isSelected}
                    aria-label={`${header.weekdayShort} ${header.dayMonth}${isToday ? " (Hoje)" : ""}${count > 0 ? `, ${count} ${count === 1 ? "item" : "itens"}` : ""}`}
                    onClick={() =>
                      setFocusedWeekDay((prev) => (prev === dayKey ? "all" : dayKey))
                    }
                    className={cn(
                      "flex min-h-14 min-w-0 flex-col items-center justify-center gap-0.5 rounded-lg border px-0.5 py-1.5 text-center transition-colors focus-visible:outline-2 focus-visible:outline-ring",
                      isSelected
                        ? "border-primary bg-primary text-primary-foreground shadow-xs"
                        : isToday
                          ? "border-primary/70 bg-accent/60 text-foreground hover:bg-accent"
                          : "border-border bg-card text-foreground hover:bg-muted",
                    )}
                  >
                    <span
                      className={cn(
                        "truncate text-[0.68rem] font-medium capitalize leading-none sm:text-xs",
                        isSelected ? "text-primary-foreground/85" : "text-muted-foreground",
                      )}
                    >
                      {header.weekdayShort.slice(0, 3)}
                    </span>
                    <span className="font-mono text-xs font-semibold leading-tight tabular-nums sm:text-sm">
                      {header.dayNumber}
                    </span>
                    <span className="flex h-3 items-center justify-center gap-0.5">
                      {hasDayConflict ? (
                        <span
                          aria-hidden
                          className={cn(
                            "size-1.5 rounded-full",
                            isSelected ? "bg-primary-foreground" : "bg-destructive",
                          )}
                        />
                      ) : count > 0 ? (
                        <span
                          className={cn(
                            "rounded-full px-1 font-mono text-[0.625rem] leading-none font-semibold",
                            isSelected
                              ? "bg-primary-foreground/20 text-primary-foreground"
                              : "bg-primary/15 text-primary",
                          )}
                        >
                          {count}
                        </span>
                      ) : isToday ? (
                        <span
                          aria-hidden
                          className={cn(
                            "size-1.5 rounded-full",
                            isSelected ? "bg-primary-foreground" : "bg-primary",
                          )}
                        />
                      ) : null}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Grade semanal de cartões responsivos */}
          <div
            className={cn(
              "grid min-w-0 gap-3",
              focusedWeekDay === "all" ? "grid-cols-1 md:grid-cols-2" : "grid-cols-1",
            )}
          >
            {visibleWeekKeys.map((dayKey) => {
              const header = formatDayHeader(dayKey);
              const dayItems = itemsByDay[dayKey] ?? [];
              const dayProposed = proposedByDay[dayKey] ?? [];
              const dayFree = freeWindowsByDay[dayKey] ?? [];
              const totalMins = dayItems.reduce(
                (acc, item) => acc + durationMinutes(item.start, item.end),
                0,
              );
              const load = getDayLoad(totalMins);
              const isToday = dayKey === todayKey;

              return (
                <Card
                  key={dayKey}
                  className={cn(
                    "min-w-0 [--card-spacing:--spacing(3.5)] sm:[--card-spacing:--spacing(4)]",
                    isToday && "border-primary/60 ring-1 ring-primary/20",
                  )}
                >
                  <CardHeader className="pb-2">
                    <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                      <div className="flex min-w-0 items-center gap-1.5">
                        <CardTitle className="truncate text-sm font-semibold capitalize">
                          {header.weekdayShort} ·{" "}
                          <span className="font-mono">{header.dayMonth}</span>
                        </CardTitle>
                        {isToday ? <Badge variant="default">Hoje</Badge> : null}
                      </div>

                      <div className="flex shrink-0 items-center gap-1.5">
                        <Badge variant={load.badgeVariant}>{load.label}</Badge>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-xs"
                          onClick={() => openCreateDialog(dayKey)}
                          aria-label={`Adicionar compromisso em ${header.dayMonth}`}
                        >
                          <Plus aria-hidden />
                        </Button>
                      </div>
                    </div>
                  </CardHeader>

                  <CardContent className="flex min-w-0 flex-col gap-2">
                    {dayItems.map((item) => (
                      <ScheduleSlotCard
                        key={item.item_id}
                        item={item}
                        timeZone={timeZone}
                        hasConflict={itemHasConflict(item, conflicts)}
                        onSelect={openEditDialog}
                      />
                    ))}

                    {dayProposed.map((block, idx) => (
                      <ProposedSlotCard
                        key={`${block.goal_id}-${dayKey}-${idx}`}
                        block={block}
                        timeZone={timeZone}
                      />
                    ))}

                    {dayItems.length === 0 && dayProposed.length === 0 ? (
                      <p className="rounded-md border border-dashed px-3 py-3 text-center text-xs text-muted-foreground">
                        Sem compromissos neste dia.
                      </p>
                    ) : null}

                    {showFreeWindows && dayFree.length > 0 ? (
                      <div className="flex min-w-0 flex-col gap-1.5 pt-1">
                        {dayFree.map((win, idx) => (
                          <FreeWindowCard
                            key={`${dayKey}-fw-${idx}`}
                            window={win}
                            timeZone={timeZone}
                            onQuickAdd={openCreateFromFreeWindow}
                          />
                        ))}
                      </div>
                    ) : null}

                    <div className="pt-1">
                      <ProtectedSleepCard preferences={schedule.preferences} compact />
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>

        {/* ==================== VISÃO HOJE ==================== */}
        <TabsContent value="hoje" className="flex min-w-0 flex-col gap-3">
          {(() => {
            const dayItems = itemsByDay[anchorDateKey] ?? [];
            const dayProposed = proposedByDay[anchorDateKey] ?? [];
            const dayFree = freeWindowsByDay[anchorDateKey] ?? [];
            const totalMins = dayItems.reduce(
              (acc, item) => acc + durationMinutes(item.start, item.end),
              0,
            );
            const load = getDayLoad(totalMins);

            return (
              <Card className="min-w-0 [--card-spacing:--spacing(3.5)] sm:[--card-spacing:--spacing(4)]">
                <CardHeader className="pb-3">
                  <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                    <CardTitle className="min-w-0 break-words text-base capitalize">
                      {formatDayHeader(anchorDateKey).fullLabel}
                    </CardTitle>
                    <Badge variant={load.badgeVariant}>{load.label}</Badge>
                  </div>
                </CardHeader>

                <CardContent className="flex min-w-0 flex-col gap-2.5">
                  {dayItems.length === 0 && dayProposed.length === 0 ? (
                    <EmptyState
                      icon={CalendarDays}
                      title="Dia livre"
                      description="Nenhum compromisso registrado nesta data. Use o botão abaixo ou uma janela livre para agendar."
                      action={
                        <Button
                          type="button"
                          onClick={() => openCreateDialog(anchorDateKey)}
                        >
                          <Plus aria-hidden />
                          Adicionar compromisso
                        </Button>
                      }
                    />
                  ) : null}

                  {dayItems.map((item) => (
                    <ScheduleSlotCard
                      key={item.item_id}
                      item={item}
                      timeZone={timeZone}
                      hasConflict={itemHasConflict(item, conflicts)}
                      onSelect={openEditDialog}
                    />
                  ))}

                  {dayProposed.map((block, idx) => (
                    <ProposedSlotCard
                      key={`${block.goal_id}-today-${idx}`}
                      block={block}
                      timeZone={timeZone}
                    />
                  ))}

                  {showFreeWindows && dayFree.length > 0 ? (
                    <div className="flex min-w-0 flex-col gap-1.5 pt-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Janelas livres reais (motor determinístico)
                      </p>
                      {dayFree.map((win, idx) => (
                        <FreeWindowCard
                          key={`today-fw-${idx}`}
                          window={win}
                          timeZone={timeZone}
                          onQuickAdd={openCreateFromFreeWindow}
                        />
                      ))}
                    </div>
                  ) : null}

                  <div className="pt-2">
                    <ProtectedSleepCard preferences={schedule.preferences} />
                  </div>
                </CardContent>
              </Card>
            );
          })()}
        </TabsContent>

        {/* ==================== VISÃO MÊS ==================== */}
        <TabsContent value="mes" className="flex min-w-0 flex-col gap-3">
          <Card className="min-w-0 [--card-spacing:--spacing(3.5)] sm:[--card-spacing:--spacing(4)]">
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle className="text-base capitalize">{monthGrid.monthLabel}</CardTitle>
                <span className="text-xs text-muted-foreground">
                  Toque em um dia para ver os detalhes
                </span>
              </div>
            </CardHeader>
            <CardContent className="px-2 sm:px-(--card-spacing)">
              <div className="grid grid-cols-7 gap-1 text-center text-[0.7rem] font-semibold text-muted-foreground sm:text-xs">
                {WEEKDAY_HEADERS.map((label) => (
                  <div key={label} className="min-w-0 truncate py-1">
                    {label}
                  </div>
                ))}
              </div>
              <div className="mt-1 grid grid-cols-7 gap-1">
                {monthGrid.days.map((dayKey) => {
                  const inMonth = dayKey.startsWith(monthGrid.currentMonthPrefix);
                  const isToday = dayKey === todayKey;
                  const dayItems = itemsByDay[dayKey] ?? [];
                  const dayProposed = proposedByDay[dayKey] ?? [];
                  const dayDeadlines = goalDeadlinesByDay[dayKey] ?? [];
                  const hasDayConflict = dayItems.some((item) =>
                    itemHasConflict(item, conflicts),
                  );

                  return (
                    <button
                      key={dayKey}
                      type="button"
                      onClick={() => {
                        setSelectedDateKey(dayKey);
                        setViewMode("hoje");
                      }}
                      className={cn(
                        "flex min-h-12 min-w-0 flex-col items-center justify-between rounded-md border p-1 text-center transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring sm:min-h-14 sm:items-start sm:p-1.5 sm:text-left",
                        !inMonth && "opacity-45",
                        isToday && "border-primary bg-accent/50",
                        hasDayConflict && "border-destructive",
                      )}
                    >
                      <span className="font-mono text-xs font-semibold tabular-nums">
                        {dayKey.slice(8, 10)}
                      </span>
                      <div className="flex max-w-full flex-wrap items-center justify-center gap-0.5 sm:justify-start sm:gap-1">
                        {dayItems.length > 0 ? (
                          <span className="rounded bg-primary/15 px-1 font-mono text-[0.625rem] font-semibold leading-tight text-primary">
                            {dayItems.length}
                          </span>
                        ) : null}
                        {dayProposed.length > 0 ? (
                          <span className="rounded border border-dashed border-slot-study-proposed px-0.5 font-mono text-[0.625rem] font-semibold leading-tight text-slot-study-proposed-fg sm:px-1">
                            +{dayProposed.length}
                          </span>
                        ) : null}
                        {dayDeadlines.length > 0 ? (
                          <span
                            className="rounded bg-warning-accent px-1 font-mono text-[0.625rem] font-semibold leading-tight text-warning-accent-foreground"
                            title={`Prazo: ${dayDeadlines.map((g) => g.title).join(", ")}`}
                          >
                            P
                          </span>
                        ) : null}
                      </div>
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Painel de Prioridades e Metas de Estudo */}
      <GoalsPanel
        goals={goals}
        timeZone={timeZone}
        anchorDateKey={anchorDateKey}
        optimizing={optimizing}
        optimizeError={optimizeError}
        onAddGoal={(goal) => {
          setGoals((prev) => [...prev, goal]);
          setOptimizeError(null);
        }}
        onRemoveGoal={(goalId) =>
          setGoals((prev) => prev.filter((item) => item.goal_id !== goalId))
        }
        onOptimize={() => void handleOptimizeWeek()}
        onOpenReallocate={() => setReallocateOpen(true)}
      />

      {/* Modal CRUD de Compromissos */}
      <ScheduleItemDialog
        open={itemDialogOpen}
        onOpenChange={setItemDialogOpen}
        preferences={schedule.preferences}
        editingItem={editingItem}
        initialDraft={itemDraft}
        onSaved={(msg) => {
          setFeedback({
            variant: "success",
            title: "Agenda atualizada",
            description: msg,
          });
          triggerReload();
        }}
      />

      {/* Modal de Rebalanceamento / Simulação de Imprevisto */}
      <ReallocateDialog
        open={reallocateOpen}
        onOpenChange={setReallocateOpen}
        preferences={schedule.preferences}
        horizon={weekHorizon}
        defaultDateKey={anchorDateKey}
        studyGoals={goals}
        onProposalReady={(proposal, req) => {
          setPendingProposal(proposal);
          setLastRequest({ type: "reallocate", payload: req });
          setProposalError(null);
          setFeedback({
            variant: "warning",
            title: "Proposta de rebalanceamento pronta para revisão",
            description:
              "Confira o diff antes/depois abaixo. Nenhuma alteração foi salva até você confirmar.",
          });
        }}
      />
    </div>
  );
}

const noopSubscribe = () => () => {};
const formatToday = () =>
  new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "numeric", month: "long" }).format(
    new Date(),
  );

/** Data de hoje no fuso do navegador; vazio no prerender (evita divergência de hidratação). */
function useTodayLabel(): string {
  return useSyncExternalStore(noopSubscribe, formatToday, () => "");
}

function useTodayKey(timeZone: string): string {
  return useSyncExternalStore(
    noopSubscribe,
    () => toDateKey(new Date(), timeZone),
    () => "2026-11-23",
  );
}
