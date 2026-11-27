"use client";

import { ArrowUp, Info, MessageSquareText, Paperclip, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { useSession } from "@/components/providers/session-provider";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { PageSkeleton } from "@/components/states/loading-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { api, isApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ChatHistoryMessage, ChatQueryResponse } from "@/types/api";

import { ChatCitations } from "./chat-citations";
import { ChatProposal } from "./chat-proposal";

type DisplayMessage = ChatHistoryMessage & {
  response?: ChatQueryResponse;
};

const SUGGESTIONS = [
  "Quais prazos acadêmicos devo acompanhar?",
  "O que dizem meus documentos sobre a Residência?",
  "Otimize minha semana com blocos de estudo.",
];

const SAFE_FAILURE = "Nenhuma resposta foi inventada e nenhuma alteração foi feita na sua agenda.";
const MAX_QUESTION_LENGTH = 4000;

function failureText(error: unknown): string {
  if (isApiError(error)) {
    if (error.kind === "unavailable") return `O assistente está temporariamente indisponível (HTTP 503). ${SAFE_FAILURE}`;
    if (error.kind === "network") return `Não foi possível conectar ao Vezo. ${SAFE_FAILURE}`;
    return `${error.message} ${SAFE_FAILURE}`;
  }
  return `Não foi possível enviar a mensagem. ${SAFE_FAILURE}`;
}

function ChatMessage({ message }: { message: DisplayMessage }) {
  const isAssistant = message.role === "assistant";
  const response = message.response;
  const abstained = message.abstained === true || response?.status === "abstained";
  const limitations = response?.limitations ?? [];
  const gaps = response?.gaps ?? [];
  const conflicts = response?.input_conflicts ?? [];

  return (
    <article className={cn("flex flex-col gap-2", isAssistant ? "items-start" : "items-end")}>
      <span className="px-1 text-xs font-medium text-muted-foreground">{isAssistant ? "Vezo" : "Você"}</span>
      <div className={cn("w-fit max-w-full rounded-xl border p-3 text-sm leading-relaxed break-words", isAssistant ? "bg-card text-card-foreground" : "bg-secondary text-secondary-foreground")}>
        {abstained && (
          <div className="mb-2 flex items-center gap-2 rounded-md bg-warning-subtle p-2 text-warning-subtle-foreground">
            <ShieldCheck aria-hidden className="size-4 shrink-0" />
            <span className="font-medium">Abstenção segura: evidências insuficientes para responder com segurança.</span>
          </div>
        )}
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
      {isAssistant && (
        <div className="w-full space-y-2">
          <ChatCitations citations={message.citations} />
          {(limitations.length > 0 || gaps.length > 0 || conflicts.length > 0) && (
            <details className="rounded-lg border border-warning bg-warning-subtle p-3 text-sm text-warning-subtle-foreground">
              <summary className="cursor-pointer font-medium">Lacunas, limitações e conflitos</summary>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {gaps.map((item, index) => <li key={`gap-${index}`}>{item}</li>)}
                {limitations.map((item, index) => <li key={`lim-${index}`}>{item}</li>)}
                {conflicts.map((item, index) => <li key={`con-${index}`}>{item}</li>)}
              </ul>
            </details>
          )}
          {/* Histórico não inclui `planning`; prévia disponível na resposta atual. */}
          {response?.planning && response.proposal_id && (
            <ChatProposal key={response.proposal_id} proposal={response.planning} proposalId={response.proposal_id} />
          )}
          {!response?.planning && message.proposal_id && (
            <p className="rounded-md border border-dashed p-2 text-xs text-muted-foreground">
              <Info aria-hidden className="mr-1 inline size-3.5" />
              Proposta vinculada à conversa. A prévia detalhada não está disponível no histórico; consulte a agenda antes de aplicar qualquer alteração.
            </p>
          )}
        </div>
      )}
    </article>
  );
}

function AuthenticatedChat() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [retryQuestion, setRetryQuestion] = useState<string | null>(null);
  const [stage, setStage] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inFlight = useRef(false);

  const loadHistory = useCallback((signal?: AbortSignal) => {
    setHistoryLoading(true);
    setHistoryError(null);
    api.chat.history(signal).then((history) => {
      if (signal?.aborted) return;
      setMessages(history);
    }).catch((error: unknown) => {
      if (signal?.aborted) return;
      setHistoryError(failureText(error));
    }).finally(() => { if (!signal?.aborted) setHistoryLoading(false); });
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    api.chat.history(controller.signal)
      .then((history) => {
        if (!controller.signal.aborted) {
          setMessages(history);
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setHistoryError(failureText(error));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setHistoryLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!pending) return;
    const interval = window.setInterval(() => setStage((current) => Math.min(2, current + 1)), 1800);
    return () => window.clearInterval(interval);
  }, [pending]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, pending]);

  async function send(value: string) {
    const normalized = value.trim();
    if (inFlight.current || normalized.length < 5 || normalized.length > MAX_QUESTION_LENGTH) return;
    inFlight.current = true;
    setPending(true);
    setStage(0);
    setSendError(null);
    setRetryQuestion(null);
    setQuestion("");
    const now = new Date().toISOString();
    const temporaryUser: DisplayMessage = {
      message_id: `local-user-${Date.now()}`, role: "user", content: normalized,
      abstained: null, citations: [], proposal_id: null, created_at: now,
    };
    setMessages((items) => [...items, temporaryUser]);
    try {
      const response = await api.chat.query({ question: normalized, include_session_schedule: true });
      const reply: DisplayMessage = {
        message_id: `local-answer-${response.run_id}`, role: "assistant", content: response.answer,
        abstained: response.abstained, citations: response.citations, proposal_id: response.proposal_id,
        created_at: new Date().toISOString(), response,
      };
      setMessages((items) => [...items, reply]);
    } catch (error) {
      setSendError(failureText(error));
      setRetryQuestion(normalized);
      setMessages((items) => items.filter((item) => item.message_id !== temporaryUser.message_id));
      setQuestion(normalized);
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send(question);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send(question);
    }
  }

  const valid = question.trim().length >= 5 && question.trim().length <= MAX_QUESTION_LENGTH;
  const stages = ["Pesquisando documentos", "Planejando", "Validando"];

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">Conversa associada à sua sessão</p>
        <span className="flex items-center gap-2 text-xs text-muted-foreground" title="Integração de documentos privados em etapa futura">
          <Paperclip aria-hidden className="size-3.5" /> Acervo Demo · Meus Documentos em breve
        </span>
      </div>
      {historyLoading && <PageSkeleton label="Carregando conversa…" />}
      {historyError && (
        <Alert variant="destructive">
          <AlertTitle>Não foi possível carregar o histórico</AlertTitle>
          <AlertDescription>{historyError}</AlertDescription>
          <Button type="button" variant="outline" size="sm" className="mt-2 w-fit" onClick={() => loadHistory()}>Tentar novamente</Button>
        </Alert>
      )}
      <div role="log" aria-live="polite" aria-label="Mensagens do chat" className="flex max-h-[55dvh] min-h-48 flex-col gap-5 overflow-y-auto rounded-lg border bg-muted/30 p-3 lg:max-h-[58dvh]">
        {!historyLoading && messages.length === 0 && !historyError && (
          <div className="m-auto flex flex-col items-center gap-2 py-7 text-center">
            <MessageSquareText aria-hidden className="size-7 text-muted-foreground" />
            <p className="font-medium">Sua conversa começa aqui</p>
            <p className="max-w-xs text-sm text-muted-foreground">Pergunte sobre editais, prazos e planejamento de estudos. As respostas mostram fontes verificáveis.</p>
          </div>
        )}
        {messages.map((message) => <ChatMessage key={message.message_id} message={message} />)}
        {pending && <div role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><span className="size-2 animate-pulse rounded-full bg-primary" />{stages[stage]}…</div>}
        <div ref={bottomRef} />
      </div>
      {sendError && (
        <Alert variant="destructive">
          <AlertTitle>Não foi possível concluir a pergunta</AlertTitle>
          <AlertDescription>{sendError}</AlertDescription>
          {retryQuestion && <Button type="button" variant="outline" size="sm" className="mt-2 w-fit" disabled={pending} onClick={() => void send(retryQuestion)}>Tentar novamente</Button>}
        </Alert>
      )}
      {messages.length === 0 && (
        <div className="flex flex-wrap gap-2" aria-label="Sugestões de perguntas">
          {SUGGESTIONS.map((suggestion) => (
            <Button key={suggestion} type="button" size="sm" variant="outline" className="h-auto min-h-11 max-w-full whitespace-normal text-left" disabled={pending} onClick={() => void send(suggestion)}>{suggestion}</Button>
          ))}
        </div>
      )}
      <form onSubmit={submit} className="space-y-2">
        <label htmlFor="vezo-chat-input" className="text-sm font-medium">Sua pergunta</label>
        <div className="flex items-end gap-2 rounded-lg border bg-card p-2">
          <textarea id="vezo-chat-input" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={onKeyDown}
            rows={2} maxLength={MAX_QUESTION_LENGTH} disabled={pending} placeholder="Pergunte ao Vezo…"
            aria-describedby="vezo-chat-hint" className="min-h-16 min-w-0 flex-1 resize-y bg-transparent p-2 text-base outline-none placeholder:text-muted-foreground" />
          <Button type="submit" size="icon" disabled={!valid || pending || historyLoading} aria-label="Enviar pergunta"><ArrowUp aria-hidden /></Button>
        </div>
        <p id="vezo-chat-hint" className="text-xs text-muted-foreground">Enter para enviar · Shift+Enter para nova linha · {question.length}/{MAX_QUESTION_LENGTH} caracteres (mínimo 5)</p>
      </form>
    </div>
  );
}

export function ChatPanel({ className }: { className?: string }) {
  const { state, refresh } = useSession();
  return (
    <section aria-labelledby="chat-titulo" className={cn("flex min-w-0 flex-col gap-4", className)}>
      <header className="flex flex-col gap-1">
        <h2 id="chat-titulo" className="text-xl font-semibold">Assistente Vezo</h2>
        <p className="text-sm text-muted-foreground">Respostas com fontes citadas. Nenhuma mudança na agenda sem sua confirmação.</p>
      </header>
      {state.status === "loading" && <PageSkeleton label="Verificando sessão…" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={() => void refresh()} />}
      {state.status === "anonymous" && (
        <EmptyState icon={MessageSquareText} title="Configure sua rotina primeiro"
          description="O assistente usa sua agenda e preferências de sono para sugerir horários."
          action={<Button asChild><Link href="/onboarding">Configurar rotina</Link></Button>} />
      )}
      {state.status === "authenticated" && <AuthenticatedChat />}
    </section>
  );
}
