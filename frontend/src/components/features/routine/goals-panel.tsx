"use client";

import {
  AlertTriangle,
  CalendarClock,
  Plus,
  Shuffle,
  Sparkles,
  Target,
  Trash2,
} from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { StudyGoal } from "@/types/api";

import {
  addDaysToKey,
  buildZonedIso,
  formatMinutes,
  formatShortDateTime,
} from "./schedule-utils";

interface GoalsPanelProps {
  goals: StudyGoal[];
  timeZone: string;
  anchorDateKey: string;
  optimizing: boolean;
  optimizeError: string | null;
  onAddGoal: (goal: StudyGoal) => void;
  onRemoveGoal: (goalId: string) => void;
  onOptimize: () => void;
  onOpenReallocate: () => void;
}

const PRIORITY_LABELS: Record<number, { text: string; variant: "destructive" | "warning" | "secondary" | "outline" }> = {
  5: { text: "P5 · Crítica", variant: "destructive" },
  4: { text: "P4 · Alta", variant: "warning" },
  3: { text: "P3 · Média", variant: "secondary" },
  2: { text: "P2 · Normal", variant: "outline" },
  1: { text: "P1 · Baixa", variant: "outline" },
};

export function GoalsPanel({
  goals,
  timeZone,
  anchorDateKey,
  optimizing,
  optimizeError,
  onAddGoal,
  onRemoveGoal,
  onOptimize,
  onOpenReallocate,
}: GoalsPanelProps) {
  const formId = useId();
  const [showForm, setShowForm] = useState(goals.length === 0);
  const [title, setTitle] = useState("");
  const [duration, setDuration] = useState("120");
  const [deadlineDate, setDeadlineDate] = useState(() => addDaysToKey(anchorDateKey, 3));
  const [deadlineTime, setDeadlineTime] = useState("21:00");
  const [priority, setPriority] = useState("4");
  const [localError, setLocalError] = useState<string | null>(null);

  const sortedGoals = [...goals].sort((a, b) => {
    const da = new Date(a.deadline).getTime();
    const db = new Date(b.deadline).getTime();
    if (da !== db) return da - db;
    return (b.priority ?? 1) - (a.priority ?? 1);
  });

  function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = title.trim();
    const mins = Number(duration);
    const prio = Number(priority);

    if (!trimmed) {
      setLocalError("Informe o título da meta de estudo.");
      return;
    }
    if (!Number.isInteger(mins) || mins < 15 || mins > 10080) {
      setLocalError("A duração deve estar entre 15 e 10080 minutos.");
      return;
    }
    if (!deadlineDate || !deadlineTime) {
      setLocalError("Informe a data e hora do prazo.");
      return;
    }

    const slug = trimmed
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 32);

    const uniqueId = `${slug || "meta"}-${Date.now().toString(36).slice(-4)}`;

    onAddGoal({
      goal_id: uniqueId,
      title: trimmed,
      duration_minutes: mins,
      deadline: buildZonedIso(deadlineDate, deadlineTime, timeZone),
      priority: Math.min(5, Math.max(1, prio || 3)),
    });

    setTitle("");
    setDuration("120");
    setLocalError(null);
    setShowForm(false);
  }

  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Target aria-hidden className="size-4 text-primary" />
            <CardTitle className="text-base">Prioridades e Metas de Estudo</CardTitle>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setShowForm((prev) => !prev)}
          >
            <Plus aria-hidden />
            {showForm ? "Fechar formulário" : "Nova meta"}
          </Button>
        </div>
        <CardDescription>
          Cadastre metas com prazo e prioridade para o motor determinístico encaixar blocos de
          estudo nas suas janelas livres (sem invadir sono ou compromissos fixos).
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {showForm ? (
          <form
            id={formId}
            onSubmit={handleAdd}
            className="flex flex-col gap-3 rounded-lg border bg-muted/40 p-3.5"
            noValidate
          >
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${formId}-title`}>Meta de estudo</Label>
              <Input
                id={`${formId}-title`}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Ex.: Revisão para Prova A1 — Econometria"
                maxLength={200}
              />
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`${formId}-dur`}>Duração (min)</Label>
                <Input
                  id={`${formId}-dur`}
                  type="number"
                  min={15}
                  max={10080}
                  step={15}
                  value={duration}
                  onChange={(e) => setDuration(e.target.value)}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`${formId}-date`}>Prazo (data)</Label>
                <Input
                  id={`${formId}-date`}
                  type="date"
                  value={deadlineDate}
                  onChange={(e) => setDeadlineDate(e.target.value)}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`${formId}-prio`}>Prioridade</Label>
                <select
                  id={`${formId}-prio`}
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  className="h-11 w-full rounded-lg border border-input bg-card px-3 text-base text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  <option value="5">5 — Crítica</option>
                  <option value="4">4 — Alta</option>
                  <option value="3">3 — Média</option>
                  <option value="2">2 — Normal</option>
                  <option value="1">1 — Baixa</option>
                </select>
              </div>
            </div>

            <div className="flex flex-wrap items-end justify-between gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`${formId}-time`}>Hora limite</Label>
                <Input
                  id={`${formId}-time`}
                  type="time"
                  value={deadlineTime}
                  onChange={(e) => setDeadlineTime(e.target.value)}
                  className="w-36"
                />
              </div>

              <Button type="submit" size="sm">
                <Plus aria-hidden />
                Adicionar meta
              </Button>
            </div>

            {localError ? (
              <p className="text-xs font-medium text-destructive-subtle-foreground">{localError}</p>
            ) : null}
          </form>
        ) : null}

        {sortedGoals.length === 0 ? (
          <p className="rounded-lg border border-dashed px-3 py-4 text-center text-sm text-muted-foreground">
            Nenhuma meta de estudo cadastrada ainda. Adicione uma meta acima para gerar uma
            proposta de otimização da semana.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {sortedGoals.map((goal) => {
              const prioInfo = PRIORITY_LABELS[goal.priority ?? 1] ?? PRIORITY_LABELS[3];
              return (
                <li
                  key={goal.goal_id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-background px-3 py-2.5"
                >
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="truncate text-sm font-semibold">{goal.title}</span>
                      <Badge variant={prioInfo.variant}>{prioInfo.text}</Badge>
                    </div>
                    <span className="inline-flex flex-wrap items-center gap-2 font-mono text-xs text-muted-foreground tabular-nums">
                      <CalendarClock aria-hidden className="size-3.5" />
                      Prazo: {formatShortDateTime(goal.deadline, timeZone)} ·{" "}
                      {formatMinutes(goal.duration_minutes)}
                    </span>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => onRemoveGoal(goal.goal_id)}
                    aria-label={`Remover meta ${goal.title}`}
                  >
                    <Trash2 aria-hidden />
                  </Button>
                </li>
              );
            })}
          </ul>
        )}

        {optimizeError ? (
          <Alert variant="destructive">
            <AlertTriangle aria-hidden />
            <AlertTitle>Não foi possível otimizar</AlertTitle>
            <AlertDescription>{optimizeError}</AlertDescription>
          </Alert>
        ) : null}

        <div className="flex flex-col gap-2 pt-1 sm:flex-row sm:flex-wrap">
          <Button
            type="button"
            disabled={goals.length === 0 || optimizing}
            onClick={onOptimize}
          >
            <Sparkles aria-hidden />
            {optimizing ? "Calculando proposta…" : "Otimizar semana"}
          </Button>
          <Button type="button" variant="secondary" onClick={onOpenReallocate}>
            <Shuffle aria-hidden />
            Simular imprevisto / Rebalancear
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
