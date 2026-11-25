"use client";

import { Lock } from "lucide-react";
import { useId } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { ChoiceGroup, FieldMessage, selectClassName } from "./onboarding-fields";
import {
  BUFFER_OPTIONS,
  MAX_BLOCK_OPTIONS,
  formatMinutesLabel,
  timezoneOptions,
  type FieldErrors,
  type WellbeingDraft,
} from "./onboarding-model";

/** Etapa 2 — Restrições de bem-estar: fuso, sono protegido, bloco máximo e intervalo. */
export function StepWellbeing({
  draft,
  onChange,
  errors,
}: {
  draft: WellbeingDraft;
  onChange: (patch: Partial<WellbeingDraft>) => void;
  errors: FieldErrors<keyof WellbeingDraft>;
}) {
  const ids = {
    timezone: useId(),
    timezoneError: useId(),
    sleepStart: useId(),
    sleepStartError: useId(),
    sleepEnd: useId(),
    sleepEndError: useId(),
    sleepHint: useId(),
    maxBlockError: useId(),
    bufferError: useId(),
  };

  const maxBlockOptions = MAX_BLOCK_OPTIONS.includes(
    draft.maxBlockMinutes as (typeof MAX_BLOCK_OPTIONS)[number],
  )
    ? MAX_BLOCK_OPTIONS
    : [...MAX_BLOCK_OPTIONS, draft.maxBlockMinutes].sort((a, b) => a - b);
  const bufferOptions = BUFFER_OPTIONS.includes(
    draft.bufferMinutes as (typeof BUFFER_OPTIONS)[number],
  )
    ? BUFFER_OPTIONS
    : [...BUFFER_OPTIONS, draft.bufferMinutes].sort((a, b) => a - b);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Label htmlFor={ids.timezone}>Fuso horário</Label>
        <select
          id={ids.timezone}
          className={selectClassName}
          value={draft.timezone}
          onChange={(event) => onChange({ timezone: event.target.value })}
          aria-invalid={errors.timezone ? true : undefined}
          aria-describedby={errors.timezone ? ids.timezoneError : undefined}
        >
          {timezoneOptions(draft.timezone).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <FieldMessage id={ids.timezoneError}>{errors.timezone}</FieldMessage>
      </div>

      <fieldset className="flex flex-col gap-3 rounded-lg border bg-card p-4">
        <legend className="flex items-center gap-2 px-1 text-sm font-semibold">
          <Lock aria-hidden className="size-4 text-slot-sleep-fg" />
          Sono protegido
        </legend>
        <p id={ids.sleepHint} className="text-sm text-muted-foreground">
          Nada será agendado nesse intervalo, nem pelo assistente. Pode atravessar a meia-noite
          (ex.: 22:00 às 06:00).
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-2">
            <Label htmlFor={ids.sleepStart}>Dormir às</Label>
            <Input
              id={ids.sleepStart}
              type="time"
              value={draft.sleepStart}
              onChange={(event) => onChange({ sleepStart: event.target.value })}
              aria-invalid={errors.sleepStart ? true : undefined}
              aria-describedby={[ids.sleepHint, errors.sleepStart ? ids.sleepStartError : ""]
                .filter(Boolean)
                .join(" ")}
              className="font-mono tabular-nums"
            />
            <FieldMessage id={ids.sleepStartError}>{errors.sleepStart}</FieldMessage>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor={ids.sleepEnd}>Acordar às</Label>
            <Input
              id={ids.sleepEnd}
              type="time"
              value={draft.sleepEnd}
              onChange={(event) => onChange({ sleepEnd: event.target.value })}
              aria-invalid={errors.sleepEnd ? true : undefined}
              aria-describedby={[ids.sleepHint, errors.sleepEnd ? ids.sleepEndError : ""]
                .filter(Boolean)
                .join(" ")}
              className="font-mono tabular-nums"
            />
            <FieldMessage id={ids.sleepEndError}>{errors.sleepEnd}</FieldMessage>
          </div>
        </div>
      </fieldset>

      <ChoiceGroup
        name="max-block"
        legend="Duração máxima de um bloco de estudo"
        description="Blocos mais curtos ajudam a manter o foco em dias cansativos."
        options={maxBlockOptions.map((value) => ({ value, label: formatMinutesLabel(value) }))}
        value={draft.maxBlockMinutes}
        onChange={(value) => onChange({ maxBlockMinutes: value })}
        error={errors.maxBlockMinutes}
        errorId={ids.maxBlockError}
      />

      <ChoiceGroup
        name="buffer"
        legend="Intervalo entre blocos"
        description="Tempo de respiro entre um compromisso e um bloco de estudo."
        options={bufferOptions.map((value) => ({ value, label: formatMinutesLabel(value) }))}
        value={draft.bufferMinutes}
        onChange={(value) => onChange({ bufferMinutes: value })}
        error={errors.bufferMinutes}
        errorId={ids.bufferError}
      />
    </div>
  );
}
