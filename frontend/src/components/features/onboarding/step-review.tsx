"use client";

import { CheckCircle2, Lock, Pencil, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import {
  KIND_LABEL,
  formatMinutesLabel,
  formatWeekdays,
  occurrenceKey,
  type CommitmentDraft,
  type StepId,
  type WellbeingDraft,
} from "./onboarding-model";
import { KIND_ICON, KIND_SLOT_CLASS } from "./step-commitments";

function ReviewSection({
  title,
  onEdit,
  editLabel,
  children,
}: {
  title: string;
  onEdit: () => void;
  editLabel: string;
  children: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3 rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-base font-semibold">{title}</h3>
        <Button type="button" variant="ghost" size="sm" onClick={onEdit} aria-label={editLabel}>
          <Pencil aria-hidden />
          Editar
        </Button>
      </div>
      {children}
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-t pt-2 first:border-t-0 first:pt-0 sm:flex-row sm:justify-between sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium sm:text-right">{children}</dd>
    </div>
  );
}

/** Etapa 4 — Resumo editável de tudo que será enviado à API. */
export function StepReview({
  consent,
  wellbeing,
  commitments,
  savedKeys,
  weekLabel,
  onGoTo,
}: {
  consent: boolean;
  wellbeing: WellbeingDraft;
  commitments: CommitmentDraft[];
  savedKeys: ReadonlySet<string>;
  weekLabel: string;
  onGoTo: (step: StepId) => void;
}) {
  const pendingCount = commitments.reduce(
    (total, c) => total + c.weekdays.filter((d) => !savedKeys.has(occurrenceKey(c.id, d))).length,
    0,
  );

  return (
    <div className="flex flex-col gap-4">
      <p className="text-base">
        Confira tudo antes de salvar. Nada é enviado até você confirmar.
      </p>

      <ReviewSection
        title="Privacidade"
        onEdit={() => onGoTo("consent")}
        editLabel="Editar consentimento"
      >
        <p className="flex items-center gap-2 text-sm">
          {consent ? (
            <>
              <ShieldCheck aria-hidden className="size-4 text-success" />
              Consentimento aceito. A data e a hora do aceite são registradas pelo servidor.
            </>
          ) : (
            <span className="text-destructive-subtle-foreground">Consentimento pendente.</span>
          )}
        </p>
      </ReviewSection>

      <ReviewSection
        title="Sono e ritmo"
        onEdit={() => onGoTo("wellbeing")}
        editLabel="Editar sono e ritmo de estudo"
      >
        <dl className="flex flex-col gap-2">
          <Row label="Fuso horário">{wellbeing.timezone}</Row>
          <Row label="Sono protegido">
            <span className="inline-flex items-center gap-1.5 font-mono tabular-nums">
              <Lock aria-hidden className="size-3.5" />
              {wellbeing.sleepStart} – {wellbeing.sleepEnd}
            </span>
          </Row>
          <Row label="Bloco máximo de estudo">{formatMinutesLabel(wellbeing.maxBlockMinutes)}</Row>
          <Row label="Intervalo entre blocos">{formatMinutesLabel(wellbeing.bufferMinutes)}</Row>
        </dl>
      </ReviewSection>

      <ReviewSection
        title="Compromissos fixos"
        onEdit={() => onGoTo("commitments")}
        editLabel="Editar compromissos fixos"
      >
        {commitments.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhum compromisso. Você pode adicioná-los depois, direto na agenda.
          </p>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              {pendingCount > 0
                ? `${pendingCount} bloco(s) fixo(s) serão criados na semana de ${weekLabel}.`
                : "Todos os compromissos já foram salvos."}
            </p>
            <ul className="flex flex-col gap-2">
              {commitments.map((c) => {
                const fullySaved = c.weekdays.every((d) => savedKeys.has(occurrenceKey(c.id, d)));
                return (
                  <li
                    key={c.id}
                    className={cn("flex items-start justify-between gap-3 rounded-lg p-3", KIND_SLOT_CLASS[c.kind])}
                  >
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <span className="flex items-center gap-1.5 text-xs font-medium">
                        <span aria-hidden>{KIND_ICON[c.kind]}</span>
                        {KIND_LABEL[c.kind]}
                      </span>
                      <span className="line-clamp-2 text-sm font-semibold">{c.label}</span>
                      <span className="font-mono text-sm tabular-nums">
                        {formatWeekdays(c.weekdays)} · <span className="whitespace-nowrap">{c.startTime} – {c.endTime}</span>
                      </span>
                    </div>
                    {fullySaved ? (
                      <Badge variant="success">
                        <CheckCircle2 aria-hidden />
                        Salvo
                      </Badge>
                    ) : (
                      <Badge variant="secondary">Fixo</Badge>
                    )}
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </ReviewSection>
    </div>
  );
}
