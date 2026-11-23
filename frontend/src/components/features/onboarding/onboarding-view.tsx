"use client";

import { CheckCircle2, Moon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";

import { useSession } from "@/components/providers/session-provider";
import { ErrorState } from "@/components/states/error-state";
import { PageSkeleton } from "@/components/states/loading-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, isApiError } from "@/lib/api";

function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Sao_Paulo";
  } catch {
    return "America/Sao_Paulo";
  }
}

const hhmm = (value: string) => value.slice(0, 5);

/**
 * Onboarding (casca). Cria a sessão no backend com consentimento LGPD e fuso do
 * navegador; o formulário completo de rotina/sono/compromissos é a #45.
 */
export function OnboardingView() {
  const { state, refresh, createSession } = useSession();
  const router = useRouter();
  const consentId = useId();
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!consent) return;
    setSubmitting(true);
    setError(null);
    try {
      await createSession({ consent_accepted: true, timezone: browserTimezone() });
      router.push("/");
    } catch (err) {
      setError(
        isApiError(err) ? err : new ApiError(0, "unknown", "Não foi possível criar sua sessão."),
      );
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-xl flex-col gap-6 px-4 py-6 lg:py-10">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold lg:text-3xl">Configurar rotina</h1>
        <p className="text-sm text-muted-foreground">
          Sua rotina, no seu ritmo. Comece criando sua sessão no Vezo.
        </p>
      </header>

      {state.status === "loading" ? <PageSkeleton /> : null}

      {state.status === "error" ? (
        <ErrorState error={state.error} onRetry={() => void refresh()} />
      ) : null}

      {state.status === "authenticated" ? (
        <>
          <Alert variant="success">
            <CheckCircle2 aria-hidden />
            <AlertTitle>Sessão ativa</AlertTitle>
            <AlertDescription>Suas preferências estão salvas neste dispositivo.</AlertDescription>
          </Alert>
          <Card>
            <CardHeader>
              <CardTitle>Preferências atuais</CardTitle>
              <CardDescription>Fuso {state.session.preferences.timezone}</CardDescription>
            </CardHeader>
            <CardContent className="flex items-center gap-3 text-sm">
              <Moon aria-hidden className="size-4 text-muted-foreground" />
              <span>
                Sono protegido das{" "}
                <time>{hhmm(state.session.preferences.sleep_start)}</time> às{" "}
                <time>{hhmm(state.session.preferences.sleep_end)}</time>
              </span>
            </CardContent>
          </Card>
          <Button asChild size="lg" className="self-start">
            <Link href="/">Ver minha rotina</Link>
          </Button>
        </>
      ) : null}

      {state.status === "anonymous" ? (
        <Card>
          <CardHeader>
            <CardTitle>Antes de começar</CardTitle>
            <CardDescription>
              O Vezo guarda sua agenda e preferências apenas para montar sua rotina. Documentos
              enviados têm dados pessoais mascarados antes da indexação.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
              <label
                htmlFor={consentId}
                className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm has-[:checked]:border-primary has-[:checked]:bg-accent"
              >
                <input
                  id={consentId}
                  type="checkbox"
                  checked={consent}
                  onChange={(event) => setConsent(event.target.checked)}
                  className="mt-0.5 size-5 shrink-0 accent-primary"
                />
                <span>
                  Concordo com o uso dos meus dados de rotina para gerar sugestões de agenda (LGPD).
                </span>
              </label>

              {error ? <ErrorState error={error} /> : null}

              <Button type="submit" size="lg" disabled={!consent || submitting}>
                {submitting ? "Criando sessão…" : "Começar"}
              </Button>
            </form>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
