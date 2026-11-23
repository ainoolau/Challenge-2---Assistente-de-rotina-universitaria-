"use client";

import {
  AlertTriangle,
  Briefcase,
  Bus,
  CalendarClock,
  CheckCircle2,
  GraduationCap,
  Lock,
  Moon,
  Pin,
  Plus,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type {
  Interval,
  ProposedBlock,
  ScheduleItemKind,
  ScheduleItemResponse,
  SessionPreferences,
} from "@/types/api";

import {
  KIND_LABELS,
  durationMinutes,
  formatMinutes,
  toLocalTimeHHMM,
} from "./schedule-utils";

const KIND_CLASS: Record<ScheduleItemKind, string> = {
  class: "vezo-slot-class",
  work: "vezo-slot-work",
  commute: "vezo-slot-commute",
  study: "vezo-slot-study-confirmed",
  sleep: "vezo-slot-sleep",
  other: "vezo-slot-work",
};

function KindIcon({ kind, className }: { kind: ScheduleItemKind; className?: string }) {
  const props = { "aria-hidden": true, className: cn("size-3.5 shrink-0", className) };
  switch (kind) {
    case "class":
      return <GraduationCap {...props} />;
    case "work":
      return <Briefcase {...props} />;
    case "commute":
      return <Bus {...props} />;
    case "sleep":
      return <Moon {...props} />;
    case "study":
      return <CheckCircle2 {...props} />;
    default:
      return <CalendarClock {...props} />;
  }
}

export function ScheduleSlotCard({
  item,
  timeZone,
  hasConflict = false,
  onSelect,
}: {
  item: ScheduleItemResponse;
  timeZone: string;
  hasConflict?: boolean;
  onSelect: (item: ScheduleItemResponse) => void;
}) {
  const start = toLocalTimeHHMM(item.start, timeZone);
  const end = toLocalTimeHHMM(item.end, timeZone);
  const mins = durationMinutes(item.start, item.end);
  const slotClass = hasConflict ? "vezo-slot-conflict" : KIND_CLASS[item.kind];

  return (
    <button
      type="button"
      onClick={() => onSelect(item)}
      className={cn(
        slotClass,
        "group flex min-h-11 w-full flex-col gap-1.5 px-3 py-2.5 text-left transition-opacity hover:opacity-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        item.kind === "commute" && "py-2",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-1.5">
        <span className="inline-flex items-center gap-1.5 font-mono text-xs font-semibold tabular-nums">
          <KindIcon kind={item.kind} />
          {start} – {end}
          <span className="font-normal opacity-80">({formatMinutes(mins)})</span>
        </span>

        <div className="flex flex-wrap items-center gap-1">
          {hasConflict ? (
            <Badge variant="destructive">
              <AlertTriangle aria-hidden />
              Conflito
            </Badge>
          ) : null}
          {item.fixed ? (
            <Badge variant="secondary">
              <Pin aria-hidden />
              Fixo
            </Badge>
          ) : (
            <Badge variant="success">Confirmado</Badge>
          )}
        </div>
      </div>

      <p className="line-clamp-2 text-sm font-semibold leading-snug">{item.label}</p>

      <div className="flex flex-wrap items-center gap-2 text-xs opacity-85">
        <span>{KIND_LABELS[item.kind]}</span>
        {item.buffer_before_minutes > 0 || item.buffer_after_minutes > 0 ? (
          <span>
            · Buffer {item.buffer_before_minutes}m / {item.buffer_after_minutes}m
          </span>
        ) : null}
      </div>
    </button>
  );
}

export function ProposedSlotCard({
  block,
  timeZone,
  tagLabel = "Proposta",
}: {
  block: ProposedBlock;
  timeZone: string;
  tagLabel?: string;
}) {
  const start = toLocalTimeHHMM(block.start, timeZone);
  const end = toLocalTimeHHMM(block.end, timeZone);
  const mins = durationMinutes(block.start, block.end);

  return (
    <div
      className="vezo-slot-study-proposed flex flex-col gap-1.5 px-3 py-2.5"
      aria-label={`Proposta pendente: ${block.title}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-1.5">
        <span className="inline-flex items-center gap-1.5 font-mono text-xs font-semibold tabular-nums">
          <Sparkles aria-hidden className="size-3.5 shrink-0" />
          {start} – {end}
          <span className="font-normal opacity-80">({formatMinutes(mins)})</span>
        </span>
        <Badge variant="proposal">{tagLabel}</Badge>
      </div>
      <p className="line-clamp-2 text-sm font-semibold leading-snug">{block.title}</p>
      <p className="text-xs opacity-85">
        Pendente de confirmação · não salvo na agenda ainda
      </p>
    </div>
  );
}

export function ProtectedSleepCard({
  preferences,
  compact = false,
}: {
  preferences: SessionPreferences;
  compact?: boolean;
}) {
  const sleepStart = preferences.sleep_start.slice(0, 5);
  const sleepEnd = preferences.sleep_end.slice(0, 5);

  return (
    <div
      className={cn(
        "vezo-slot-sleep flex flex-col gap-1 px-3",
        compact ? "py-2" : "py-2.5",
      )}
      aria-label={`Sono protegido das ${sleepStart} às ${sleepEnd}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-1.5">
        <span className="inline-flex items-center gap-1.5 font-mono text-xs font-semibold tabular-nums">
          <Moon aria-hidden className="size-3.5 shrink-0" />
          {sleepStart} – {sleepEnd}
        </span>
        <Badge variant="outline" className="border-slot-sleep bg-slot-sleep-bg text-slot-sleep-fg">
          <Lock aria-hidden />
          Sono protegido
        </Badge>
      </div>
      {!compact ? (
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs opacity-90">
          <span>Bloqueado contra alocação automática ({preferences.timezone}).</span>
          <Link
            href="/onboarding"
            className="font-medium underline underline-offset-4 hover:opacity-100"
          >
            Ajustar em preferências
          </Link>
        </div>
      ) : null}
    </div>
  );
}

export function FreeWindowCard({
  window,
  timeZone,
  onQuickAdd,
}: {
  window: Interval;
  timeZone: string;
  onQuickAdd?: (window: Interval) => void;
}) {
  const start = toLocalTimeHHMM(window.start, timeZone);
  const end = toLocalTimeHHMM(window.end, timeZone);
  const mins = durationMinutes(window.start, window.end);

  return (
    <div className="flex items-center justify-between gap-2 rounded-md border border-dashed border-border bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-mono font-medium text-foreground tabular-nums">
          {start} – {end}
        </span>
        <span>· Janela livre ({formatMinutes(mins)})</span>
      </div>
      {onQuickAdd ? (
        <Button
          type="button"
          variant="ghost"
          size="xs"
          onClick={() => onQuickAdd(window)}
          aria-label={`Adicionar compromisso na janela livre ${start} às ${end}`}
        >
          <Plus aria-hidden />
          Agendar
        </Button>
      ) : null}
    </div>
  );
}
