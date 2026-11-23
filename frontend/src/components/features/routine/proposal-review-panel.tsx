"use client";

import {
  AlertTriangle,
  ArrowRight,
  Check,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { ApiError } from "@/lib/api";
import type { ScheduleProposalResponse, StudyGoal } from "@/types/api";

import {
  classifyConflictError,
  durationMinutes,
  formatMinutes,
  formatShortDateTime,
  toLocalTimeHHMM,
} from "./schedule-utils";

interface ProposalReviewPanelProps {
  proposal: ScheduleProposalResponse;
  timeZone: string;
  goalsById: Record<string, StudyGoal>;
  busyAction: "confirm" | "reject" | "recalculate" | null;
  actionError: ApiError | null;
  onConfirm: () => void;
  onReject: () => void;
  onRecalculate?: () => void;
}

export function ProposalReviewPanel({
  proposal,
  timeZone,
  goalsById,
  busyAction,
  actionError,
  onConfirm,
  onReject,
  onRecalculate,
}: ProposalReviewPanelProps) {
  const isReallocate = proposal.proposal_type === "reallocate" && proposal.rebalance !== null;
  const rebalance = proposal.rebalance;
  const planning = proposal.planning;

  const diffSummary = rebalance?.diff_summary ?? planning?.diff_summary ?? "";
  const unallocated = rebalance?.unallocated ?? planning?.unallocated ?? [];
  const reasons = rebalance?.reasons ?? [];
  const proposedBlocks = rebalance?.proposed_blocks ?? planning?.proposed_blocks ?? [];

  const isVersionConflict =
    actionError?.kind === "conflict" && classifyConflictError(actionError.message) === "version";

  const goalLabel = (goalId: string) => goalsById[goalId]?.title ?? goalId;

  return (
    <Card className="border-2 border-dashed border-slot-study-proposed bg-card">
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Sparkles aria-hidden className="size-4 text-slot-study-proposed" />
            <CardTitle className="text-lg">
              {isReallocate ? "Revisar proposta de rebalanceamento" : "Revisar proposta de estudos"}
            </CardTitle>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="proposal">Pendente · Requer confirmação</Badge>
            <Badge variant="outline" className="font-mono">
              base v{proposal.base_version}
            </Badge>
          </div>
        </div>
        <CardDescription>
          Nenhuma alteração foi gravada na sua agenda. Os blocos tracejados abaixo só serão
          aplicados após você clicar em <strong>Confirmar e aplicar</strong>.
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {diffSummary ? (
          <div className="rounded-lg border bg-muted/60 px-3 py-2.5 text-sm text-foreground">
            {diffSummary}
          </div>
        ) : null}

        {reasons.length > 0 ? (
          <div className="flex flex-col gap-1.5">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Justificativas do motor determinístico
            </p>
            <ul className="list-disc space-y-1 pl-5 text-sm text-foreground">
              {reasons.map((reason, idx) => (
                <li key={idx}>{reason}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {isReallocate && rebalance ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2">
              <Badge variant="proposal">+{rebalance.diff.added.length} adicionados</Badge>
              <Badge variant="warning">{rebalance.diff.moved.length} movidos</Badge>
              <Badge variant="secondary">{rebalance.diff.kept.length} preservados</Badge>
              {rebalance.diff.removed.length > 0 ? (
                <Badge variant="destructive">{rebalance.diff.removed.length} removidos</Badge>
              ) : null}
            </div>

            {rebalance.diff.moved.length > 0 ? (
              <div className="flex flex-col gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Blocos movidos (antes → depois)
                </p>
                <ul className="flex flex-col gap-2">
                  {rebalance.diff.moved.map((m, idx) => (
                    <li
                      key={`${m.goal_id}-${idx}`}
                      className="vezo-slot-study-proposed flex flex-col gap-1.5 px-3 py-2.5 text-sm"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-semibold">{m.title}</span>
                        <Badge variant="warning">Movido</Badge>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5 font-mono text-xs tabular-nums">
                        <span className="line-through opacity-75">
                          {formatShortDateTime(m.previous_start, timeZone)}–
                          {toLocalTimeHHMM(m.previous_end, timeZone)}
                        </span>
                        <ArrowRight aria-hidden className="size-3.5 shrink-0" />
                        <span className="font-semibold">
                          {formatShortDateTime(m.new_start, timeZone)}–
                          {toLocalTimeHHMM(m.new_end, timeZone)}
                        </span>
                      </div>
                      <p className="text-xs opacity-90">{m.reason}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {rebalance.diff.added.length > 0 ? (
              <div className="flex flex-col gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Novos blocos sugeridos
                </p>
                <ul className="flex flex-col gap-2">
                  {rebalance.diff.added.map((block, idx) => (
                    <li
                      key={`${block.goal_id}-add-${idx}`}
                      className="vezo-slot-study-proposed flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
                    >
                      <div>
                        <p className="font-semibold">{block.title}</p>
                        <p className="font-mono text-xs tabular-nums">
                          {formatShortDateTime(block.start, timeZone)}–
                          {toLocalTimeHHMM(block.end, timeZone)} (
                          {formatMinutes(durationMinutes(block.start, block.end))})
                        </p>
                      </div>
                      <Badge variant="proposal">+ Adicionado</Badge>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {rebalance.diff.removed.length > 0 ? (
              <div className="flex flex-col gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Blocos removidos / fragmentados
                </p>
                <ul className="flex flex-col gap-1.5">
                  {rebalance.diff.removed.map((block, idx) => (
                    <li
                      key={`${block.goal_id}-rem-${idx}`}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-destructive/40 bg-destructive-subtle px-3 py-2 text-xs text-destructive-subtle-foreground"
                    >
                      <span className="line-through font-medium">{block.title}</span>
                      <span className="font-mono tabular-nums">
                        {formatShortDateTime(block.start, timeZone)}–
                        {toLocalTimeHHMM(block.end, timeZone)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {rebalance.diff.kept.length > 0 ? (
              <div className="flex flex-col gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Blocos preservados sem alteração (mínima perturbação)
                </p>
                <ul className="flex flex-col gap-1.5">
                  {rebalance.diff.kept.map((block, idx) => (
                    <li
                      key={`${block.goal_id}-kept-${idx}`}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/40 px-3 py-2 text-xs text-foreground"
                    >
                      <span className="font-medium">{block.title}</span>
                      <span className="font-mono text-muted-foreground tabular-nums">
                        {formatShortDateTime(block.start, timeZone)}–
                        {toLocalTimeHHMM(block.end, timeZone)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Blocos sugeridos ({proposedBlocks.length})
            </p>
            {proposedBlocks.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nenhum bloco pôde ser encaixado nas janelas livres deste horizonte.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {proposedBlocks.map((block, idx) => (
                  <li
                    key={`${block.goal_id}-${idx}`}
                    className="vezo-slot-study-proposed flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
                  >
                    <div>
                      <p className="font-semibold">{block.title}</p>
                      <p className="font-mono text-xs tabular-nums">
                        {formatShortDateTime(block.start, timeZone)}–
                        {toLocalTimeHHMM(block.end, timeZone)} (
                        {formatMinutes(durationMinutes(block.start, block.end))})
                      </p>
                    </div>
                    <Badge variant="proposal">Proposta</Badge>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {unallocated.length > 0 ? (
          <Alert variant="warning">
            <AlertTriangle aria-hidden />
            <AlertTitle>Minutos não alocados (sono e fixos preservados)</AlertTitle>
            <AlertDescription>
              <ul className="mt-1 list-disc space-y-0.5 pl-4">
                {unallocated.map((u) => (
                  <li key={u.goal_id}>
                    <strong>{goalLabel(u.goal_id)}</strong>: faltaram{" "}
                    <span className="font-mono font-semibold">
                      {formatMinutes(u.remaining_minutes)}
                    </span>{" "}
                    antes do prazo sem invadir sono protegido ou compromissos fixos.
                  </li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        ) : (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck aria-hidden className="size-4 text-success" />
            <span>
              Auditoria determinística aprovada: zero invasões de sono protegido ou compromissos
              fixos.
            </span>
          </div>
        )}

        {actionError ? (
          <Alert variant="destructive">
            <AlertTriangle aria-hidden />
            <AlertTitle>
              {isVersionConflict
                ? "Agenda desatualizada (conflito de versão 409)"
                : "Não foi possível aplicar a proposta"}
            </AlertTitle>
            <AlertDescription className="flex flex-col gap-2">
              <span>{actionError.message}</span>
              {isVersionConflict && onRecalculate ? (
                <div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={busyAction !== null}
                    onClick={onRecalculate}
                  >
                    <RefreshCw aria-hidden />
                    {busyAction === "recalculate"
                      ? "Recalculando…"
                      : "Recalcular proposta na versão atual"}
                  </Button>
                </div>
              ) : null}
            </AlertDescription>
          </Alert>
        ) : null}
      </CardContent>

      <Separator />

      <CardFooter className="flex flex-col-reverse gap-2 pt-4 sm:flex-row sm:justify-end">
        <Button
          type="button"
          variant="outline"
          disabled={busyAction !== null}
          onClick={onReject}
        >
          <X aria-hidden />
          {busyAction === "reject" ? "Descartando…" : "Descartar"}
        </Button>
        <Button
          type="button"
          disabled={busyAction !== null || isVersionConflict}
          onClick={onConfirm}
        >
          <Check aria-hidden />
          {busyAction === "confirm" ? "Aplicando…" : "Confirmar e aplicar"}
        </Button>
      </CardFooter>
    </Card>
  );
}
