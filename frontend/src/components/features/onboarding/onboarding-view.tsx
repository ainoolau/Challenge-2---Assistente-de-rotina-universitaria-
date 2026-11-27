"use client";

import { ArrowLeft, ArrowRight, Check, Loader2, ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useSession } from "@/components/providers/session-provider";
import { ErrorState } from "@/components/states/error-state";
import { PageSkeleton } from "@/components/states/loading-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError, api, isApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { SessionPreferences } from "@/types/api";

import { formatDayHeader, getWeekKeys, toDateKey } from "../routine/schedule-utils";
import {
  STEPS,
  describeFieldErrors,
  expandOccurrences,
  hasErrors,
  initialWellbeing,
  toPreferencesUpdate,
  toSessionCreate,
  validateWellbeing,
  type CommitmentDraft,
  type FieldErrors,
  type StepId,
  type WellbeingDraft,
} from "./onboarding-model";
import { StepCommitments, type CommitmentFailure } from "./step-commitments";
import { StepConsent } from "./step-consent";
import { StepReview } from "./step-review";
import { StepWellbeing } from "./step-wellbeing";

function toApiError(error: unknown, fallback: string): ApiError {
  return isApiError(error) ? error : new ApiError(0, "unknown", fallback);
}

/**
 * Onboarding (TASK-F1-02): consentimento LGPD → bem-estar → compromissos fixos →
 * revisão. Cria a sessão (POST /sessions) ou atualiza preferências (PUT /preferences)
 * e persiste os compromissos (POST /schedule), tratando 409/422 em português.
 */
export function OnboardingView() {
  const { state, refresh } = useSession();

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-6 lg:py-10">
      {state.status === "loading" ? <PageSkeleton /> : null}
      {state.status === "error" ? (
        <ErrorState error={state.error} onRetry={() => void refresh()} />
      ) : null}
      {state.status === "anonymous" || state.status === "authenticated" ? (
        <OnboardingWizard
          initialPrefs={state.status === "authenticated" ? state.session.preferences : null}
        />
      ) : null}
    </div>
  );
}

function OnboardingWizard({ initialPrefs }: { initialPrefs: SessionPreferences | null }) {
  const { state, createSession, refresh } = useSession();
  const router = useRouter();
  const [hadSessionAtStart] = useState(initialPrefs !== null);
  const [today] = useState(() => new Date());
  const sessionPrefs = state.status === "authenticated" ? state.session.preferences : null;

  const [stepIndex, setStepIndex] = useState(0);
  const [consent, setConsent] = useState(initialPrefs?.consent_accepted ?? false);
  const [consentError, setConsentError] = useState<string>();
  const [wellbeing, setWellbeing] = useState<WellbeingDraft>(() => initialWellbeing(initialPrefs));
  const [wellbeingErrors, setWellbeingErrors] = useState<FieldErrors<keyof WellbeingDraft>>({});
  const [commitments, setCommitments] = useState<CommitmentDraft[]>([]);
  const [editing, setEditing] = useState<CommitmentDraft | null>(null);
  const [stepError, setStepError] = useState<string>();

  const [savedKeys, setSavedKeys] = useState<ReadonlySet<string>>(() => new Set());
  const [failures, setFailures] = useState<Record<string, CommitmentFailure>>({});
  const [submitError, setSubmitError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState<string>();

  const step = STEPS[stepIndex] ?? STEPS[0];
  const headingRef = useRef<HTMLHeadingElement>(null);
  const firstRender = useRef(true);

  // Move o foco para o título da etapa a cada troca (leitores de tela e teclado).
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    headingRef.current?.focus();
  }, [stepIndex]);

  const todayKey = toDateKey(today, wellbeing.timezone);
  const weekKeys = getWeekKeys(todayKey);
  const weekLabel = `${formatDayHeader(weekKeys[0] ?? "").dayMonth} a ${
    formatDayHeader(weekKeys[6] ?? "").dayMonth
  }`;
  const failureCount = Object.keys(failures).length;

  function goTo(id: StepId) {
    const index = STEPS.findIndex((s) => s.id === id);
    if (index >= 0) {
      setStepError(undefined);
      setStepIndex(index);
    }
  }

  function validateStep(id: StepId): boolean {
    if (id === "consent") {
      const error = consent ? undefined : "Para continuar, marque a caixa de consentimento.";
      setConsentError(error);
      return !error;
    }
    if (id === "wellbeing") {
      const errors = validateWellbeing(wellbeing);
      setWellbeingErrors(errors);
      return !hasErrors(errors);
    }
    if (id === "commitments" && editing) {
      setStepError("Adicione à lista ou cancele o compromisso em edição antes de continuar.");
      return false;
    }
    return true;
  }

  function next() {
    setStepError(undefined);
    if (!validateStep(step.id)) {
      headingRef.current?.focus();
      return;
    }
    setStepIndex((i) => Math.min(i + 1, STEPS.length - 1));
  }

  function back() {
    setStepError(undefined);
    setStepIndex((i) => Math.max(i - 1, 0));
  }

  async function handleSubmit() {
    // Revalida tudo: o usuário pode ter voltado e editado etapas anteriores.
    for (const s of STEPS) {
      if (!validateStep(s.id)) {
        goTo(s.id);
        return;
      }
    }

    setSubmitting(true);
    setSubmitError(null);
    setFailures({});

    // 1) Sessão + preferências (consent_accepted; o backend grava consent_timestamp).
    try {
      setProgress(sessionPrefs ? "Atualizando preferências…" : "Criando sua sessão…");
      if (sessionPrefs) {
        await api.preferences.replace(toPreferencesUpdate(wellbeing, sessionPrefs));
      } else {
        await createSession(toSessionCreate(wellbeing));
      }
    } catch (error) {
      setSubmitError(toApiError(error, "Não foi possível salvar suas preferências."));
      setSubmitting(false);
      setProgress(undefined);
      return;
    }

    // 2) Compromissos fixos — só os que ainda não foram salvos (retentativa segura).
    const pending = expandOccurrences(commitments, wellbeing.timezone, today).filter(
      (occurrence) => !savedKeys.has(occurrence.key),
    );
    const saved = new Set(savedKeys);
    const found: Record<string, CommitmentFailure> = {};
    let fatal: ApiError | null = null;

    for (const [index, occurrence] of pending.entries()) {
      setProgress(`Salvando compromissos (${index + 1} de ${pending.length})…`);
      try {
        await api.schedule.create(occurrence.payload);
        saved.add(occurrence.key);
      } catch (error) {
        const apiError = toApiError(error, "Não foi possível salvar este compromisso.");
        if (["network", "unauthorized", "unavailable", "unknown"].includes(apiError.kind)) {
          fatal = apiError;
          break;
        }
        const isSleep = apiError.kind === "conflict" && apiError.message.toLowerCase().includes("sono");
        const message = isSleep
          ? `invade seu sono protegido (${wellbeing.sleepStart}–${wellbeing.sleepEnd}). Ajuste o horário ou o sono.`
          : apiError.kind === "validation"
            ? describeFieldErrors(apiError.fieldErrors).join(" ") || apiError.message
            : apiError.message;
        const previous = found[occurrence.commitmentId];
        found[occurrence.commitmentId] = {
          labels: [...(previous?.labels ?? []), occurrence.slotLabel],
          message,
          kind: isSleep ? "sleep" : apiError.kind === "validation" ? "validation" : "other",
        };
      }
    }

    setSavedKeys(saved);
    setFailures(found);
    setProgress(undefined);

    if (fatal || Object.keys(found).length > 0) {
      setSubmitError(fatal);
      setSubmitting(false);
      return;
    }

    router.push("/");
    void refresh();
  }

  const isLast = step.id === "review";
  const sleepFailure = Object.values(failures).some((f) => f.kind === "sleep");

  return (
    <>
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold lg:text-3xl">
          {hadSessionAtStart ? "Ajustar rotina" : "Configurar rotina"}
        </h1>
        <p className="text-sm text-muted-foreground">
          {hadSessionAtStart
            ? "Revise suas preferências e adicione novos compromissos fixos."
            : "Sua rotina, no seu ritmo. Leva cerca de 2 minutos."}
        </p>
      </header>

      <nav aria-label="Etapas do onboarding">
        <ol className="grid grid-cols-4 gap-2">
          {STEPS.map((s, index) => {
            const done = index < stepIndex;
            const current = index === stepIndex;
            return (
              <li key={s.id} className="flex flex-col gap-1.5">
                <span
                  aria-hidden
                  className={cn(
                    "h-1 rounded-full",
                    done || current ? "bg-primary" : "bg-border",
                  )}
                />
                <button
                  type="button"
                  onClick={() => goTo(s.id)}
                  disabled={index > stepIndex || submitting}
                  aria-current={current ? "step" : undefined}
                  className={cn(
                    "flex min-h-11 min-w-0 items-start gap-1 rounded-md text-left text-xs font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-default",
                    current ? "text-foreground" : "text-muted-foreground",
                    done && "hover:text-foreground",
                  )}
                >
                  {done ? <Check aria-hidden className="mt-px hidden size-3.5 shrink-0 sm:block" /> : null}
                  <span className="min-w-0 truncate">
                    <span className="sr-only">
                      Etapa {index + 1}{done ? " (concluída)" : ""}:{" "}
                    </span>
                    {s.short}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      <section aria-labelledby="onboarding-step-title" className="flex flex-col gap-5">
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium text-muted-foreground">
            Etapa {stepIndex + 1} de {STEPS.length}
          </p>
          <h2
            id="onboarding-step-title"
            ref={headingRef}
            tabIndex={-1}
            className="text-xl font-semibold outline-none"
          >
            {step.title}
          </h2>
        </div>

        {step.id === "consent" ? (
          <StepConsent
            consent={consent}
            onConsentChange={(value) => {
              setConsent(value);
              if (value) setConsentError(undefined);
            }}
            error={consentError}
          />
        ) : null}

        {step.id === "wellbeing" ? (
          <StepWellbeing
            draft={wellbeing}
            onChange={(patch) => {
              const merged = { ...wellbeing, ...patch };
              setWellbeing(merged);
              if (hasErrors(wellbeingErrors)) setWellbeingErrors(validateWellbeing(merged));
            }}
            errors={wellbeingErrors}
          />
        ) : null}

        {step.id === "commitments" ? (
          <>
            {hadSessionAtStart ? (
              <p className="text-sm text-muted-foreground">
                Compromissos já salvos continuam na sua agenda. Aqui você adiciona novos.
              </p>
            ) : null}
            <StepCommitments
              commitments={commitments}
              defaultDateKey={todayKey}
              onChange={(nextList) => {
                setCommitments(nextList);
                setStepError(undefined);
              }}
              savedKeys={savedKeys}
              failures={failures}
              editing={editing}
              onEditingChange={(draft) => {
                setEditing(draft);
                setStepError(undefined);
              }}
            />
          </>
        ) : null}

        {step.id === "review" ? (
          <>
            {failureCount > 0 ? (
              <Alert variant="destructive">
                <ShieldAlert aria-hidden />
                <AlertTitle>
                  {failureCount === 1
                    ? "1 compromisso não foi salvo"
                    : `${failureCount} compromissos não foram salvos`}
                </AlertTitle>
                <AlertDescription className="flex flex-col gap-2">
                  <ul className="list-disc pl-4">
                    {commitments
                      .filter((c) => failures[c.id])
                      .map((c) => (
                        <li key={c.id}>
                          <strong>{c.label}</strong> ({(failures[c.id]?.labels ?? []).join(", ")}):{" "}
                          {failures[c.id]?.message}
                        </li>
                      ))}
                  </ul>
                  <p>
                    Sua sessão e os demais itens já foram salvos. Corrija e confirme de novo: só o que
                    falta será enviado.
                  </p>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Button type="button" variant="outline" onClick={() => goTo("commitments")}>
                      Editar compromissos
                    </Button>
                    {sleepFailure ? (
                      <Button type="button" variant="outline" onClick={() => goTo("wellbeing")}>
                        Ajustar horário de sono
                      </Button>
                    ) : null}
                  </div>
                </AlertDescription>
              </Alert>
            ) : null}

            {submitError ? (
              <Alert variant="destructive">
                <ShieldAlert aria-hidden />
                <AlertTitle>
                  {submitError.kind === "validation"
                    ? "Revise alguns campos"
                    : submitError.kind === "conflict"
                      ? "Regra protegida da agenda"
                      : "Não foi possível salvar"}
                </AlertTitle>
                <AlertDescription>
                  {submitError.kind === "validation" && submitError.fieldErrors.length > 0 ? (
                    <ul className="list-disc pl-4">
                      {describeFieldErrors(submitError.fieldErrors).map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  ) : (
                    submitError.message
                  )}
                </AlertDescription>
              </Alert>
            ) : null}

            <StepReview
              consent={consent}
              wellbeing={wellbeing}
              commitments={commitments}
              savedKeys={savedKeys}
              weekLabel={weekLabel}
              onGoTo={goTo}
            />
          </>
        ) : null}

        {stepError ? (
          <p role="alert" className="text-sm text-destructive-subtle-foreground">
            {stepError}
          </p>
        ) : null}
      </section>

      <div className="flex flex-col-reverse gap-2 border-t pt-4 sm:flex-row sm:justify-between">
        {stepIndex > 0 ? (
          <Button type="button" variant="ghost" onClick={back} disabled={submitting}>
            <ArrowLeft aria-hidden />
            Voltar
          </Button>
        ) : (
          <span aria-hidden className="hidden sm:block" />
        )}
        {isLast ? (
          <Button type="button" size="lg" onClick={() => void handleSubmit()} disabled={submitting}>
            {submitting ? <Loader2 aria-hidden className="animate-spin" /> : <Check aria-hidden />}
            {submitting ? (progress ?? "Salvando…") : "Confirmar e salvar"}
          </Button>
        ) : (
          <Button type="button" size="lg" onClick={next}>
            Continuar
            <ArrowRight aria-hidden />
          </Button>
        )}
      </div>

      <p aria-live="polite" className="sr-only">
        {progress ?? ""}
      </p>
    </>
  );
}
