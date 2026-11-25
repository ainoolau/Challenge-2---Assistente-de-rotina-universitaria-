"use client";

import {
  Briefcase,
  Bus,
  CheckCircle2,
  Flag,
  GraduationCap,
  Pencil,
  Plus,
  ShieldAlert,
  Trash2,
  Wand2,
} from "lucide-react";
import { useId, useState, type ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

import { ChoiceGroup, FieldMessage } from "./onboarding-fields";
import {
  KIND_LABEL,
  KIND_OPTIONS,
  WEEKDAYS,
  emptyCommitment,
  exampleScenario,
  formatWeekdays,
  hasErrors,
  occurrenceKey,
  validateCommitment,
  type CommitmentDraft,
  type CommitmentField,
  type CommitmentKind,
  type FieldErrors,
} from "./onboarding-model";

export const KIND_ICON: Record<CommitmentKind, ReactNode> = {
  class: <GraduationCap className="size-4" />,
  work: <Briefcase className="size-4" />,
  commute: <Bus className="size-4" />,
  other: <Flag className="size-4" />,
};

/** Classes de domínio de `tokens.css` (DESIGN.md §3.3). */
export const KIND_SLOT_CLASS: Record<CommitmentKind, string> = {
  class: "vezo-slot-class",
  work: "vezo-slot-work",
  commute: "vezo-slot-commute",
  other: "border bg-card",
};

export interface CommitmentFailure {
  /** Dias (0–6) que o backend recusou. */
  weekdays: number[];
  message: string;
  kind: "sleep" | "validation" | "other";
}

interface StepCommitmentsProps {
  commitments: CommitmentDraft[];
  onChange: (next: CommitmentDraft[]) => void;
  savedKeys: ReadonlySet<string>;
  failures: Record<string, CommitmentFailure>;
  /** Compromisso aberto no editor (estado elevado para o wizard bloquear "Continuar"). */
  editing: CommitmentDraft | null;
  onEditingChange: (draft: CommitmentDraft | null) => void;
}

/** Etapa 3 — Compromissos fixos da semana (multijornada). */
export function StepCommitments({
  commitments,
  onChange,
  savedKeys,
  failures,
  editing,
  onEditingChange: setEditing,
}: StepCommitmentsProps) {
  const isNew = editing ? !commitments.some((c) => c.id === editing.id) : false;

  function save(draft: CommitmentDraft) {
    onChange(
      isNew ? [...commitments, draft] : commitments.map((c) => (c.id === draft.id ? draft : c)),
    );
    setEditing(null);
  }

  function savedDays(commitment: CommitmentDraft): number[] {
    return commitment.weekdays.filter((d) => savedKeys.has(occurrenceKey(commitment.id, d)));
  }

  return (
    <div className="flex flex-col gap-5">
      <p className="text-base">
        Cadastre o que já ocupa sua semana. O Vezo nunca move compromissos fixos e só sugere estudo
        nos espaços livres.
      </p>

      {commitments.length === 0 ? null : (
        <ul className="flex flex-col gap-2" aria-label="Compromissos cadastrados">
          {commitments.map((commitment) => {
            const saved = savedDays(commitment);
            const fullySaved = saved.length === commitment.weekdays.length;
            const failure = failures[commitment.id];
            if (editing?.id === commitment.id) return null;
            return (
              <li
                key={commitment.id}
                className={cn(
                  "flex flex-col gap-2 rounded-lg p-3",
                  KIND_SLOT_CLASS[commitment.kind],
                  failure && "vezo-slot-conflict",
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 flex-col gap-1">
                    <span className="flex items-center gap-1.5 text-xs font-medium">
                      <span aria-hidden>{KIND_ICON[commitment.kind]}</span>
                      {KIND_LABEL[commitment.kind]}
                    </span>
                    <span className="line-clamp-2 font-semibold">{commitment.label}</span>
                    <span className="font-mono text-sm tabular-nums">
                      {formatWeekdays(commitment.weekdays)} · <span className="whitespace-nowrap">{commitment.startTime} – {commitment.endTime}</span>
                    </span>
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    {fullySaved ? (
                      <Badge variant="success">
                        <CheckCircle2 aria-hidden />
                        Salvo
                      </Badge>
                    ) : (
                      <>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => setEditing(commitment)}
                          aria-label={`Editar ${commitment.label}`}
                        >
                          <Pencil aria-hidden />
                        </Button>
                        {saved.length === 0 ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={() => onChange(commitments.filter((c) => c.id !== commitment.id))}
                            aria-label={`Remover ${commitment.label}`}
                          >
                            <Trash2 aria-hidden />
                          </Button>
                        ) : null}
                      </>
                    )}
                  </div>
                </div>
                {saved.length > 0 && !fullySaved ? (
                  <p className="text-xs">
                    {formatWeekdays(saved)} já salvo(s). Alterações valem só para os dias restantes.
                  </p>
                ) : null}
                {failure ? (
                  <p className="flex items-start gap-2 text-sm font-medium" role="status">
                    <ShieldAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
                    <span>
                      {formatWeekdays(failure.weekdays)}: {failure.message}
                    </span>
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      {editing ? (
        <CommitmentEditor
          key={editing.id}
          initial={editing}
          isNew={isNew}
          lockedWeekdays={savedDays(editing)}
          onSave={save}
          onCancel={() => setEditing(null)}
        />
      ) : (
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button type="button" variant="outline" onClick={() => setEditing(emptyCommitment())}>
            <Plus aria-hidden />
            Adicionar compromisso
          </Button>
        </div>
      )}

      {savedKeys.size === 0 ? (
        <div className="flex flex-col gap-2 rounded-lg border border-dashed p-4">
          <p className="text-sm text-muted-foreground">
            Só quer ver o Vezo funcionando? Carregue uma semana fictícia de multijornada (residência,
            aulas noturnas, deslocamento e uma entrega).
          </p>
          <Button
            type="button"
            variant="secondary"
            className="self-start"
            onClick={() => {
              onChange(exampleScenario());
              setEditing(null);
            }}
          >
            <Wand2 aria-hidden />
            {commitments.length > 0 ? "Substituir pelo cenário exemplo" : "Carregar cenário exemplo"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function CommitmentEditor({
  initial,
  isNew,
  lockedWeekdays,
  onSave,
  onCancel,
}: {
  initial: CommitmentDraft;
  isNew: boolean;
  lockedWeekdays: number[];
  onSave: (draft: CommitmentDraft) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState(initial);
  const [errors, setErrors] = useState<FieldErrors<CommitmentField>>({});
  const ids = {
    label: useId(),
    labelError: useId(),
    kindError: useId(),
    weekdaysError: useId(),
    start: useId(),
    startError: useId(),
    end: useId(),
    endError: useId(),
  };

  function patch(next: Partial<CommitmentDraft>) {
    const merged = { ...draft, ...next };
    setDraft(merged);
    // Revalida só os campos que já mostravam erro, para não "gritar" enquanto digita.
    if (hasErrors(errors)) {
      const fresh = validateCommitment(merged);
      setErrors(
        Object.fromEntries(
          Object.entries(fresh).filter(([field]) => field in errors),
        ) as FieldErrors<CommitmentField>,
      );
    }
  }

  function toggleDay(day: number) {
    if (lockedWeekdays.includes(day)) return;
    patch({
      weekdays: draft.weekdays.includes(day)
        ? draft.weekdays.filter((d) => d !== day)
        : [...draft.weekdays, day],
    });
  }

  function submit() {
    const found = validateCommitment(draft);
    setErrors(found);
    if (hasErrors(found)) {
      const first = found.label ? ids.label : found.startTime ? ids.start : found.endTime ? ids.end : null;
      if (first) document.getElementById(first)?.focus();
      return;
    }
    onSave({ ...draft, label: draft.label.trim() });
  }

  return (
    <div
      role="group"
      aria-label={isNew ? "Novo compromisso" : "Editar compromisso"}
      className="flex flex-col gap-4 rounded-lg border bg-card p-4"
    >
      <h3 className="text-base font-semibold">{isNew ? "Novo compromisso" : "Editar compromisso"}</h3>

      <ChoiceGroup
        name={`kind-${initial.id}`}
        legend="Tipo"
        options={KIND_OPTIONS.map((option) => ({ ...option, icon: KIND_ICON[option.value] }))}
        value={draft.kind}
        onChange={(kind) => patch({ kind })}
        errorId={ids.kindError}
        columns="two"
      />

      <div className="flex flex-col gap-2">
        <Label htmlFor={ids.label}>Nome</Label>
        <Input
          id={ids.label}
          value={draft.label}
          maxLength={200}
          placeholder={draft.kind === "other" ? "Ex.: Entrega do TCC" : "Ex.: Aula de Cálculo"}
          onChange={(event) => patch({ label: event.target.value })}
          aria-invalid={errors.label ? true : undefined}
          aria-describedby={errors.label ? ids.labelError : undefined}
          autoComplete="off"
        />
        <FieldMessage id={ids.labelError}>{errors.label}</FieldMessage>
      </div>

      <fieldset
        className="flex flex-col gap-2"
        aria-describedby={errors.weekdays ? ids.weekdaysError : undefined}
      >
        <legend className="mb-1 text-sm font-medium">Dias da semana</legend>
        <div className="grid grid-cols-7 gap-1">
          {WEEKDAYS.map((day, index) => {
            const pressed = draft.weekdays.includes(index);
            const locked = lockedWeekdays.includes(index);
            return (
              <button
                key={day.short}
                type="button"
                aria-pressed={pressed}
                aria-label={`${day.long}${locked ? " (já salvo)" : ""}`}
                disabled={locked}
                onClick={() => toggleDay(index)}
                className={cn(
                  "flex h-11 items-center justify-center rounded-lg border text-sm font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-60",
                  pressed
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card hover:bg-muted",
                )}
              >
                {day.short}
              </button>
            );
          })}
        </div>
        <FieldMessage id={ids.weekdaysError}>{errors.weekdays}</FieldMessage>
      </fieldset>

      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-2">
          <Label htmlFor={ids.start}>{draft.kind === "other" ? "Reservar das" : "Início"}</Label>
          <Input
            id={ids.start}
            type="time"
            value={draft.startTime}
            onChange={(event) => patch({ startTime: event.target.value })}
            aria-invalid={errors.startTime ? true : undefined}
            aria-describedby={errors.startTime ? ids.startError : undefined}
            className="font-mono tabular-nums"
          />
          <FieldMessage id={ids.startError}>{errors.startTime}</FieldMessage>
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor={ids.end}>{draft.kind === "other" ? "Até" : "Término"}</Label>
          <Input
            id={ids.end}
            type="time"
            value={draft.endTime}
            onChange={(event) => patch({ endTime: event.target.value })}
            aria-invalid={errors.endTime ? true : undefined}
            aria-describedby={errors.endTime ? ids.endError : undefined}
            className="font-mono tabular-nums"
          />
          <FieldMessage id={ids.endError}>{errors.endTime}</FieldMessage>
        </div>
      </div>

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="button" onClick={submit}>
          {isNew ? "Adicionar à lista" : "Salvar alterações"}
        </Button>
      </div>
    </div>
  );
}
