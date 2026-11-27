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

import { MODALITY_LABELS, MODALITY_OPTIONS } from "../routine/schedule-utils";
import { ChoiceGroup, FieldMessage } from "./onboarding-fields";
import {
  FREQUENCY_OPTIONS,
  KIND_LABEL,
  KIND_OPTIONS,
  WEEKDAYS,
  commitmentOccurrenceKeys,
  emptyCommitment,
  exampleScenario,
  formatCommitmentSchedule,
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
  /** Rótulos dos dias/datas que o backend recusou (ex.: "Seg", "28/11"). */
  labels: string[];
  message: string;
  kind: "sleep" | "validation" | "other";
}

interface StepCommitmentsProps {
  commitments: CommitmentDraft[];
  defaultDateKey: string;
  onChange: (next: CommitmentDraft[]) => void;
  savedKeys: ReadonlySet<string>;
  failures: Record<string, CommitmentFailure>;
  /** Compromisso aberto no editor (estado elevado para o wizard bloquear "Continuar"). */
  editing: CommitmentDraft | null;
  onEditingChange: (draft: CommitmentDraft | null) => void;
}

/** Etapa 3 — Compromissos fixos e compromissos pontuais com data. */
export function StepCommitments({
  commitments,
  defaultDateKey,
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
    if (commitment.frequency !== "weekly") return [];
    return commitment.weekdays.filter((d) => savedKeys.has(occurrenceKey(commitment.id, d)));
  }

  return (
    <div className="flex flex-col gap-5">
      <p className="text-base">
        Cadastre seus compromissos fixos da semana ou eventos pontuais com data (como provas e
        consultas). O Vezo nunca move esses horários e só sugere estudo nos espaços livres.
      </p>

      {commitments.length === 0 ? null : (
        <ul className="flex flex-col gap-2" aria-label="Compromissos cadastrados">
          {commitments.map((commitment) => {
            const allKeys = commitmentOccurrenceKeys(commitment);
            const saved = savedDays(commitment);
            const savedCount = allKeys.filter((k) => savedKeys.has(k)).length;
            const fullySaved = allKeys.length > 0 && savedCount === allKeys.length;
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
                    <span className="flex flex-wrap items-center gap-1.5 text-xs font-medium">
                      <span aria-hidden>{KIND_ICON[commitment.kind]}</span>
                      <span>{KIND_LABEL[commitment.kind]}</span>
                      {commitment.modality !== "presencial" ? (
                        <span>· {MODALITY_LABELS[commitment.modality]}</span>
                      ) : null}
                      {commitment.allowOverlap ? <span>· Paralelo</span> : null}
                    </span>
                    <span className="line-clamp-2 font-semibold">{commitment.label}</span>
                    <span className="font-mono text-sm tabular-nums">
                      {formatCommitmentSchedule(commitment)} ·{" "}
                      <span className="whitespace-nowrap">
                        {commitment.startTime} – {commitment.endTime}
                      </span>
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
                        {savedCount === 0 ? (
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
                      {failure.labels.join(", ")}: {failure.message}
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
          <Button
            type="button"
            variant="outline"
            onClick={() => setEditing(emptyCommitment("class", defaultDateKey))}
          >
            <Plus aria-hidden />
            Adicionar compromisso
          </Button>
        </div>
      )}

      {savedKeys.size === 0 ? (
        <div className="flex flex-col gap-2 rounded-lg border border-dashed p-4">
          <p className="text-sm text-muted-foreground">
            Só quer testar o Vezo rapidamente? Carregue uma rotina de exemplo com trabalho, aulas,
            deslocamento e um compromisso pontual.
          </p>
          <Button
            type="button"
            variant="secondary"
            className="self-start"
            onClick={() => {
              onChange(exampleScenario(defaultDateKey));
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
    freqError: useId(),
    date: useId(),
    dateError: useId(),
    weekdaysError: useId(),
    modalityError: useId(),
    overlap: useId(),
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
      const first = found.label
        ? ids.label
        : found.dateKey
          ? ids.date
          : found.startTime
            ? ids.start
            : found.endTime
              ? ids.end
              : null;
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
        legend="Categoria"
        options={KIND_OPTIONS.map((option) => ({ ...option, icon: KIND_ICON[option.value] }))}
        value={draft.kind}
        onChange={(kind) =>
          patch({
            kind,
            ...(kind === "other" && draft.weekdays.length === 0 ? { frequency: "once" } : {}),
          })
        }
        errorId={ids.kindError}
        columns="two"
      />

      <div className="flex flex-col gap-2">
        <Label htmlFor={ids.label}>Nome</Label>
        <Input
          id={ids.label}
          value={draft.label}
          maxLength={200}
          placeholder={
            draft.kind === "other"
              ? "Ex.: Consulta médica ou Prova de Cálculo"
              : draft.kind === "work"
                ? "Ex.: Estágio ou Trabalho"
                : draft.kind === "commute"
                  ? "Ex.: Ônibus até a faculdade"
                  : "Ex.: Aula de Cálculo"
          }
          onChange={(event) => patch({ label: event.target.value })}
          aria-invalid={errors.label ? true : undefined}
          aria-describedby={errors.label ? ids.labelError : undefined}
          autoComplete="off"
        />
        <FieldMessage id={ids.labelError}>{errors.label}</FieldMessage>
      </div>

      {lockedWeekdays.length === 0 ? (
        <ChoiceGroup
          name={`freq-${initial.id}`}
          legend="Frequência"
          options={FREQUENCY_OPTIONS}
          value={draft.frequency}
          onChange={(frequency) => patch({ frequency })}
          errorId={ids.freqError}
          columns="two"
        />
      ) : null}

      {draft.frequency === "once" ? (
        <div className="flex flex-col gap-2">
          <Label htmlFor={ids.date}>Data</Label>
          <Input
            id={ids.date}
            type="date"
            value={draft.dateKey}
            onChange={(event) => patch({ dateKey: event.target.value })}
            aria-invalid={errors.dateKey ? true : undefined}
            aria-describedby={errors.dateKey ? ids.dateError : undefined}
          />
          <FieldMessage id={ids.dateError}>{errors.dateKey}</FieldMessage>
        </div>
      ) : (
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
      )}

      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-2">
          <Label htmlFor={ids.start}>Início</Label>
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
          <Label htmlFor={ids.end}>Término</Label>
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

      <ChoiceGroup
        name={`modality-${initial.id}`}
        legend="Modalidade"
        description="Compromissos remotos não reservam tempo automático de deslocamento."
        options={MODALITY_OPTIONS.map((value) => ({ value, label: MODALITY_LABELS[value] }))}
        value={draft.modality}
        onChange={(modality) => patch({ modality })}
        errorId={ids.modalityError}
      />

      <label
        htmlFor={ids.overlap}
        className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm has-[:checked]:border-primary has-[:checked]:bg-accent"
      >
        <input
          id={ids.overlap}
          type="checkbox"
          checked={draft.allowOverlap}
          onChange={(event) => patch({ allowOverlap: event.target.checked })}
          className="mt-0.5 size-5 shrink-0 accent-primary"
        />
        <span>
          <strong>Pode ocorrer em paralelo</strong> — permite coexistir com outro compromisso no
          mesmo horário sem gerar alerta de conflito.
        </span>
      </label>

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
