"use client";

import { AlertTriangle, Shuffle } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api, isApiError } from "@/lib/api";
import type {
  Interval,
  ReallocateScheduleRequest,
  ScheduleProposalResponse,
  ScheduleSlotKind,
  SessionPreferences,
  StudyGoal,
} from "@/types/api";

import { KIND_LABELS, buildZonedIso } from "./schedule-utils";

const DISRUPTION_KINDS: readonly Exclude<ScheduleSlotKind, "sleep">[] = [
  "work",
  "class",
  "commute",
  "other",
] as const;

interface ReallocateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  preferences: SessionPreferences;
  horizon: Interval;
  defaultDateKey: string;
  studyGoals: StudyGoal[];
  onProposalReady: (
    proposal: ScheduleProposalResponse,
    request: ReallocateScheduleRequest,
  ) => void;
}

export function ReallocateDialog({
  open,
  onOpenChange,
  preferences,
  horizon,
  defaultDateKey,
  studyGoals,
  onProposalReady,
}: ReallocateDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? (
        <ReallocateDialogBody
          key={defaultDateKey}
          onClose={() => onOpenChange(false)}
          preferences={preferences}
          horizon={horizon}
          defaultDateKey={defaultDateKey}
          studyGoals={studyGoals}
          onProposalReady={onProposalReady}
        />
      ) : null}
    </Dialog>
  );
}

function ReallocateDialogBody({
  onClose,
  preferences,
  horizon,
  defaultDateKey,
  studyGoals,
  onProposalReady,
}: Omit<ReallocateDialogProps, "open" | "onOpenChange"> & { onClose: () => void }) {
  const formId = useId();
  const [label, setLabel] = useState("Reunião extraordinária / Imprevisto");
  const [kind, setKind] = useState<Exclude<ScheduleSlotKind, "sleep">>("work");
  const [dateKey, setDateKey] = useState(defaultDateKey);
  const [startTime, setStartTime] = useState("14:00");
  const [endTime, setEndTime] = useState("16:00");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!label.trim()) {
      setError("Descreva o imprevisto para calcular o rebalanceamento.");
      return;
    }
    if (!startTime || !endTime || endTime <= startTime) {
      setError("O término do imprevisto deve ser posterior ao início.");
      return;
    }

    setError(null);
    setSubmitting(true);

    const request: ReallocateScheduleRequest = {
      horizon,
      disruptions: [
        {
          label: label.trim(),
          kind,
          fixed: true,
          start: buildZonedIso(dateKey, startTime, preferences.timezone),
          end: buildZonedIso(dateKey, endTime, preferences.timezone),
        },
      ],
      study_goals: studyGoals,
      disruption_note: note.trim() || null,
    };

    try {
      const proposal = await api.schedule.reallocate(request);
      onProposalReady(proposal, request);
      onClose();
    } catch (err) {
      const apiErr = isApiError(err)
        ? err
        : new ApiError(0, "unknown", "Não foi possível simular o rebalanceamento.");
      setError(apiErr.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shuffle aria-hidden className="size-4 text-primary" />
            Simular imprevisto e rebalancear
          </DialogTitle>
          <DialogDescription>
            O Vezo preserva seu sono, seus compromissos fixos e os estudos não afetados, mostrando
            uma prévia das mudanças antes de salvar.
          </DialogDescription>
        </DialogHeader>

        <form id={formId} onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`${formId}-label`}>Imprevisto</Label>
            <Input
              id={`${formId}-label`}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Ex.: Plantão extra ou entrega urgente"
              maxLength={200}
              required
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex min-w-0 flex-col gap-1.5">
              <Label htmlFor={`${formId}-kind`}>Tipo</Label>
              <select
                id={`${formId}-kind`}
                value={kind}
                onChange={(e) => setKind(e.target.value as Exclude<ScheduleSlotKind, "sleep">)}
                className="h-11 w-full min-w-0 rounded-lg border border-input bg-card px-3 text-base text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                {DISRUPTION_KINDS.map((k) => (
                  <option key={k} value={k}>
                    {KIND_LABELS[k]}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex min-w-0 flex-col gap-1.5">
              <Label htmlFor={`${formId}-date`}>Data</Label>
              <Input
                id={`${formId}-date`}
                type="date"
                value={dateKey}
                onChange={(e) => setDateKey(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex min-w-0 flex-col gap-1.5">
              <Label htmlFor={`${formId}-start`}>Início</Label>
              <Input
                id={`${formId}-start`}
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                required
              />
            </div>
            <div className="flex min-w-0 flex-col gap-1.5">
              <Label htmlFor={`${formId}-end`}>Término</Label>
              <Input
                id={`${formId}-end`}
                type="time"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="flex min-w-0 flex-col gap-1.5">
            <Label htmlFor={`${formId}-note`}>Observação (opcional)</Label>
            <Input
              id={`${formId}-note`}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Ex.: Reunião remarcada de última hora"
              maxLength={500}
            />
          </div>

          {error ? (
            <Alert variant="destructive">
              <AlertTriangle aria-hidden />
              <AlertTitle>Não foi possível simular</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
        </form>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            disabled={submitting}
            onClick={onClose}
            className="w-full sm:w-auto"
          >
            Cancelar
          </Button>
          <Button
            type="submit"
            form={formId}
            disabled={submitting}
            className="h-auto min-h-11 w-full whitespace-normal py-2 text-center sm:w-auto"
          >
            {submitting ? "Calculando nova proposta…" : "Gerar proposta de rebalanceamento"}
          </Button>
        </DialogFooter>
      </DialogContent>
  );
}
