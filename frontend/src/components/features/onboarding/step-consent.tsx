"use client";

import { Clock, Database, EyeOff, Info, ShieldCheck, Target } from "lucide-react";
import { useId, type ReactNode } from "react";

import { FieldMessage } from "./onboarding-fields";

function Topic({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section className="flex gap-3 border-t py-4 first:border-t-0 first:pt-0">
      <span aria-hidden className="mt-0.5 text-muted-foreground">
        {icon}
      </span>
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-semibold">{title}</h3>
        <div className="flex flex-col gap-1 text-sm text-muted-foreground">{children}</div>
      </div>
    </section>
  );
}

/**
 * Etapa 1 — Transparência LGPD e consentimento explícito.
 * Texto sujeito a revisão da equipe: não afirma conformidade jurídica automática.
 */
export function StepConsent({
  consent,
  onConsentChange,
  error,
}: {
  consent: boolean;
  onConsentChange: (value: boolean) => void;
  error?: string;
}) {
  const checkboxId = useId();
  const errorId = useId();

  return (
    <div className="flex flex-col gap-5">
      <p className="text-base">
        Antes de configurar sua rotina, veja com clareza quais dados o Vezo usa, para quê e por
        quanto tempo.
      </p>

      <div className="flex flex-col rounded-lg border bg-card p-4">
        <Topic icon={<Database className="size-5" />} title="O que guardamos">
          <p>
            Fuso horário, horário de sono, preferências de bloco de estudo e os compromissos que você
            cadastrar (nome, tipo, dia e horário).
          </p>
          <p>Não pedimos nome, e-mail, CPF, matrícula ou telefone.</p>
        </Topic>
        <Topic icon={<Target className="size-5" />} title="Para que usamos">
          <p>
            Somente para montar sua agenda, proteger seu sono e sugerir blocos de estudo. Nenhuma
            sugestão muda sua agenda sem a sua confirmação.
          </p>
        </Topic>
        <Topic icon={<ShieldCheck className="size-5" />} title="Como tratamos">
          <p>
            Sua sessão é identificada por um cookie protegido no navegador, sem conta nem senha. Os
            dados ficam no servidor do Vezo e não são vendidos nem usados para publicidade.
          </p>
          <p>
            Quando você usa o assistente, o texto da pergunta e trechos relevantes da sua agenda podem
            ser processados por um provedor de modelo de linguagem para gerar a resposta.
          </p>
        </Topic>
        <Topic icon={<Clock className="size-5" />} title="Por quanto tempo">
          <p>
            O Vezo é um MVP acadêmico. Os dados ficam guardados enquanto a sessão existir no ambiente
            de demonstração. Ainda não há exclusão automática por prazo; você pode pedir a exclusão
            à equipe a qualquer momento.
          </p>
        </Topic>
        <Topic icon={<EyeOff className="size-5" />} title="O que é opcional">
          <p>
            Compromissos são opcionais: sem eles o Vezo só terá menos contexto. Se preferir, use nomes
            genéricos como “Aula” ou “Plantão”.
          </p>
        </Topic>
      </div>

      <div className="flex flex-col gap-2">
        <label
          htmlFor={checkboxId}
          className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border bg-card p-3 text-sm has-[:checked]:border-primary has-[:checked]:bg-accent has-[:checked]:text-accent-foreground has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50"
        >
          <input
            id={checkboxId}
            type="checkbox"
            checked={consent}
            onChange={(event) => onConsentChange(event.target.checked)}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? errorId : undefined}
            className="mt-0.5 size-5 shrink-0 accent-primary"
          />
          <span>
            Li e concordo com o uso dos meus dados de rotina para as finalidades acima.
          </span>
        </label>
        <FieldMessage id={errorId}>{error}</FieldMessage>
      </div>

      <p className="flex items-start gap-2 text-xs text-muted-foreground">
        <Info aria-hidden className="mt-0.5 size-3.5 shrink-0" />
        Texto em revisão pela equipe do projeto. Não é um parecer jurídico de conformidade com a
        LGPD.
      </p>
    </div>
  );
}
