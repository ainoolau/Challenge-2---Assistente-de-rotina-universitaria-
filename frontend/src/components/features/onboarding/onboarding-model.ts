/**
 * Modelo do onboarding (TASK-F1-02): rascunho local, validações de cliente,
 * cenário de exemplo e conversão para os contratos da API FastAPI.
 *
 * Regras de privacidade (LGPD — minimização):
 * - O rascunho vive apenas no estado React do formulário: nada de localStorage,
 *   contexto global ou console.log.
 * - O cenário de exemplo é 100% fictício (sem nomes, matrícula ou instituição).
 * - Toda regra de agenda (sono protegido, conflitos) é decidida pelo backend;
 *   aqui só validamos formato e coerência básica dos campos.
 */

import type { FieldError } from "@/lib/api";
import type {
  PreferencesUpdateRequest,
  ScheduleItemCreate,
  ScheduleModality,
  SessionCreateRequest,
  SessionPreferences,
} from "@/types/api";

import {
  addDaysToKey,
  buildZonedIso,
  formatDayHeader,
  getWeekKeys,
  toDateKey,
} from "../routine/schedule-utils";

// ---------------------------------------------------------------------------
// Tipos do rascunho
// ---------------------------------------------------------------------------

export const DEFAULT_TIMEZONE = "America/Sao_Paulo";

/** Tipos aceitos no onboarding. */
export type CommitmentKind = "class" | "work" | "commute" | "other";

/** Frequência do compromisso no onboarding: recorrente na semana ou em data única. */
export type CommitmentFrequency = "weekly" | "once";

export interface WellbeingDraft {
  timezone: string;
  /** "HH:MM" */
  sleepStart: string;
  /** "HH:MM" */
  sleepEnd: string;
  maxBlockMinutes: number;
  bufferMinutes: number;
}

export interface CommitmentDraft {
  id: string;
  kind: CommitmentKind;
  label: string;
  frequency: CommitmentFrequency;
  /** Índices 0 (segunda) a 6 (domingo) da semana atual (usado quando frequency === "weekly"). */
  weekdays: number[];
  /** Data específica "YYYY-MM-DD" (usada quando frequency === "once"). */
  dateKey: string;
  /** "HH:MM" */
  startTime: string;
  /** "HH:MM" */
  endTime: string;
  modality: ScheduleModality;
  allowOverlap: boolean;
}

export type StepId = "consent" | "wellbeing" | "commitments" | "review";

export const STEPS: readonly { id: StepId; title: string; short: string }[] = [
  { id: "consent", title: "Transparência e consentimento", short: "Privacidade" },
  { id: "wellbeing", title: "Sono e ritmo de estudo", short: "Bem-estar" },
  { id: "commitments", title: "Compromissos fixos", short: "Agenda" },
  { id: "review", title: "Revisar antes de salvar", short: "Revisão" },
] as const;

export const KIND_OPTIONS: readonly { value: CommitmentKind; label: string; hint: string }[] = [
  { value: "class", label: "Aula", hint: "Disciplinas, laboratórios ou monitorias" },
  { value: "work", label: "Trabalho", hint: "Emprego, estágio ou plantão" },
  { value: "commute", label: "Deslocamento", hint: "Trajeto de ônibus, metrô ou carro" },
  { value: "other", label: "Outro compromisso", hint: "Provas, consultas, entregas ou eventos" },
] as const;

export const KIND_LABEL: Record<CommitmentKind, string> = {
  class: "Aula",
  work: "Trabalho",
  commute: "Deslocamento",
  other: "Outro compromisso",
};

export const FREQUENCY_OPTIONS: readonly {
  value: CommitmentFrequency;
  label: string;
  hint: string;
}[] = [
  { value: "weekly", label: "Toda semana", hint: "Repete nos dias escolhidos" },
  { value: "once", label: "Data específica", hint: "Prova, consulta ou evento pontual" },
] as const;

export const WEEKDAYS: readonly { short: string; long: string }[] = [
  { short: "Seg", long: "segunda-feira" },
  { short: "Ter", long: "terça-feira" },
  { short: "Qua", long: "quarta-feira" },
  { short: "Qui", long: "quinta-feira" },
  { short: "Sex", long: "sexta-feira" },
  { short: "Sáb", long: "sábado" },
  { short: "Dom", long: "domingo" },
] as const;

export const MAX_BLOCK_OPTIONS = [30, 45, 60, 90, 120] as const;
export const BUFFER_OPTIONS = [0, 10, 15, 30] as const;

/** Fusos brasileiros mais comuns com rótulos amigáveis; o valor interno segue padrão IANA. */
const BRAZIL_TIMEZONES: readonly { value: string; label: string }[] = [
  { value: "America/Sao_Paulo", label: "Horário de Brasília" },
  { value: "America/Manaus", label: "Amazonas" },
  { value: "America/Cuiaba", label: "Mato Grosso" },
  { value: "America/Belem", label: "Pará" },
  { value: "America/Fortaleza", label: "Ceará" },
  { value: "America/Recife", label: "Pernambuco" },
  { value: "America/Bahia", label: "Bahia" },
  { value: "America/Rio_Branco", label: "Acre" },
  { value: "America/Noronha", label: "Fernando de Noronha" },
];

export function formatTimezoneLabel(value: string): string {
  return BRAZIL_TIMEZONES.find((item) => item.value === value)?.label ?? value;
}

export function timezoneOptions(current: string): { value: string; label: string }[] {
  const options = [...BRAZIL_TIMEZONES];
  const extras = [current, browserTimezone()].filter(
    (tz, index, all) => tz && all.indexOf(tz) === index,
  );
  for (const tz of extras) {
    if (!options.some((option) => option.value === tz)) {
      options.push({ value: tz, label: `${tz} (detectado)` });
    }
  }
  return options;
}

export function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || DEFAULT_TIMEZONE;
  } catch {
    return DEFAULT_TIMEZONE;
  }
}

export function isValidTimezone(value: string): boolean {
  if (!value) return false;
  try {
    new Intl.DateTimeFormat("pt-BR", { timeZone: value });
    return true;
  } catch {
    return false;
  }
}

const hhmm = (value: string) => value.slice(0, 5);

export function initialWellbeing(prefs: SessionPreferences | null): WellbeingDraft {
  if (!prefs) {
    return {
      timezone: DEFAULT_TIMEZONE,
      sleepStart: "22:00",
      sleepEnd: "06:00",
      maxBlockMinutes: 60,
      bufferMinutes: 10,
    };
  }
  return {
    timezone: prefs.timezone,
    sleepStart: hhmm(prefs.sleep_start),
    sleepEnd: hhmm(prefs.sleep_end),
    maxBlockMinutes: prefs.max_block_minutes,
    bufferMinutes: prefs.buffer_minutes,
  };
}

let idCounter = 0;
export function newCommitmentId(): string {
  idCounter += 1;
  return `c${Date.now().toString(36)}${idCounter}`;
}

export function emptyCommitment(
  kind: CommitmentKind = "class",
  defaultDateKey = "",
): CommitmentDraft {
  return {
    id: newCommitmentId(),
    kind,
    label: "",
    frequency: kind === "other" ? "once" : "weekly",
    weekdays: [],
    dateKey: defaultDateKey,
    startTime: "",
    endTime: "",
    modality: "presencial",
    allowOverlap: false,
  };
}

/**
 * Cenário fictício de multijornada para teste rápido (trabalho + aulas noturnas
 * + deslocamento + um compromisso pontual). Nenhum dado pessoal real.
 */
export function exampleScenario(defaultDateKey: string): CommitmentDraft[] {
  return [
    {
      id: newCommitmentId(),
      kind: "commute",
      label: "Trajeto até o trabalho",
      frequency: "weekly",
      weekdays: [0, 2, 4],
      dateKey: defaultDateKey,
      startTime: "06:20",
      endTime: "07:00",
      modality: "presencial",
      allowOverlap: false,
    },
    {
      id: newCommitmentId(),
      kind: "work",
      label: "Expediente de estágio",
      frequency: "weekly",
      weekdays: [0, 2, 4],
      dateKey: defaultDateKey,
      startTime: "07:00",
      endTime: "13:00",
      modality: "presencial",
      allowOverlap: false,
    },
    {
      id: newCommitmentId(),
      kind: "class",
      label: "Aula de Estatística",
      frequency: "weekly",
      weekdays: [1, 3],
      dateKey: defaultDateKey,
      startTime: "19:00",
      endTime: "21:30",
      modality: "presencial",
      allowOverlap: false,
    },
    {
      id: newCommitmentId(),
      kind: "other",
      label: "Consulta médica",
      frequency: "once",
      weekdays: [],
      dateKey: addDaysToKey(defaultDateKey, 2),
      startTime: "16:00",
      endTime: "17:00",
      modality: "presencial",
      allowOverlap: false,
    },
  ];
}

// ---------------------------------------------------------------------------
// Validações de cliente (formato e coerência — regras de agenda ficam no backend)
// ---------------------------------------------------------------------------

export type FieldErrors<K extends string> = Partial<Record<K, string>>;

export function validateWellbeing(
  draft: WellbeingDraft,
): FieldErrors<keyof WellbeingDraft> {
  const errors: FieldErrors<keyof WellbeingDraft> = {};
  if (!isValidTimezone(draft.timezone)) errors.timezone = "Escolha um fuso horário válido.";
  if (!draft.sleepStart) errors.sleepStart = "Informe quando seu sono começa.";
  if (!draft.sleepEnd) errors.sleepEnd = "Informe quando seu sono termina.";
  if (draft.sleepStart && draft.sleepEnd && draft.sleepStart === draft.sleepEnd) {
    errors.sleepEnd = "O fim do sono precisa ser diferente do início.";
  }
  if (draft.maxBlockMinutes < 15 || draft.maxBlockMinutes > 240) {
    errors.maxBlockMinutes = "Escolha entre 15 e 240 minutos.";
  }
  if (draft.bufferMinutes < 0 || draft.bufferMinutes > 120) {
    errors.bufferMinutes = "Escolha entre 0 e 120 minutos.";
  }
  return errors;
}

export type CommitmentField = "label" | "weekdays" | "dateKey" | "startTime" | "endTime";

export function validateCommitment(draft: CommitmentDraft): FieldErrors<CommitmentField> {
  const errors: FieldErrors<CommitmentField> = {};
  const label = draft.label.trim();
  if (!label) errors.label = "Dê um nome ao compromisso.";
  else if (label.length > 200) errors.label = "Use no máximo 200 caracteres.";
  if (draft.frequency === "weekly" && draft.weekdays.length === 0) {
    errors.weekdays = "Selecione pelo menos um dia.";
  }
  if (draft.frequency === "once" && !draft.dateKey) {
    errors.dateKey = "Escolha a data do compromisso.";
  }
  if (!draft.startTime) errors.startTime = "Informe o horário de início.";
  if (!draft.endTime) errors.endTime = "Informe o horário de término.";
  if (draft.startTime && draft.endTime && draft.endTime <= draft.startTime) {
    errors.endTime = "O término precisa ser depois do início (no mesmo dia).";
  }
  return errors;
}

export const hasErrors = (errors: object) => Object.keys(errors).length > 0;

// ---------------------------------------------------------------------------
// Conversão para contratos da API
// ---------------------------------------------------------------------------

const toApiTime = (value: string) => `${value}:00`;

export function toSessionCreate(draft: WellbeingDraft): SessionCreateRequest {
  return {
    timezone: draft.timezone,
    sleep_start: toApiTime(draft.sleepStart),
    sleep_end: toApiTime(draft.sleepEnd),
    buffer_minutes: draft.bufferMinutes,
    max_block_minutes: draft.maxBlockMinutes,
    consent_accepted: true,
  };
}

export function toPreferencesUpdate(
  draft: WellbeingDraft,
  current: SessionPreferences | null,
): PreferencesUpdateRequest {
  return {
    timezone: draft.timezone,
    sleep_start: toApiTime(draft.sleepStart),
    sleep_end: toApiTime(draft.sleepEnd),
    buffer_minutes: draft.bufferMinutes,
    max_block_minutes: draft.maxBlockMinutes,
    // Evita 422 se o mínimo salvo antes for maior que o novo máximo.
    min_block_minutes: Math.min(current?.min_block_minutes ?? 1, draft.maxBlockMinutes),
    consent_accepted: true,
  };
}

/** Chave estável de uma ocorrência (compromisso + dia da semana ou data específica). */
export const occurrenceKey = (commitmentId: string, slot: string | number) =>
  `${commitmentId}|${slot}`;

export interface Occurrence {
  key: string;
  commitmentId: string;
  slotLabel: string;
  payload: ScheduleItemCreate;
}

/** Retorna todas as chaves de ocorrência previstas para um compromisso. */
export function commitmentOccurrenceKeys(commitment: CommitmentDraft): string[] {
  if (commitment.frequency === "once") {
    return commitment.dateKey ? [occurrenceKey(commitment.id, commitment.dateKey)] : [];
  }
  return [...commitment.weekdays]
    .sort((a, b) => a - b)
    .map((weekday) => occurrenceKey(commitment.id, weekday));
}

/**
 * Expande cada compromisso nos dias selecionados (semanal na semana atual ou
 * data única escolhida), já com offset explícito exigido pela API.
 */
export function expandOccurrences(
  commitments: CommitmentDraft[],
  timezone: string,
  now: Date = new Date(),
): Occurrence[] {
  const weekKeys = getWeekKeys(toDateKey(now, timezone));
  const occurrences: Occurrence[] = [];
  for (const commitment of commitments) {
    if (commitment.frequency === "once") {
      if (!commitment.dateKey) continue;
      const header = formatDayHeader(commitment.dateKey);
      occurrences.push({
        key: occurrenceKey(commitment.id, commitment.dateKey),
        commitmentId: commitment.id,
        slotLabel: `${header.weekdayShort} ${header.dayMonth}`,
        payload: {
          label: commitment.label.trim(),
          kind: commitment.kind,
          fixed: true,
          modality: commitment.modality,
          allow_overlap: commitment.allowOverlap,
          start: buildZonedIso(commitment.dateKey, commitment.startTime, timezone),
          end: buildZonedIso(commitment.dateKey, commitment.endTime, timezone),
        },
      });
      continue;
    }

    for (const weekday of [...commitment.weekdays].sort((a, b) => a - b)) {
      const dateKey = weekKeys[weekday];
      if (!dateKey) continue;
      occurrences.push({
        key: occurrenceKey(commitment.id, weekday),
        commitmentId: commitment.id,
        slotLabel: WEEKDAYS[weekday]?.short ?? "",
        payload: {
          label: commitment.label.trim(),
          kind: commitment.kind,
          fixed: true,
          modality: commitment.modality,
          allow_overlap: commitment.allowOverlap,
          start: buildZonedIso(dateKey, commitment.startTime, timezone),
          end: buildZonedIso(dateKey, commitment.endTime, timezone),
        },
      });
    }
  }
  return occurrences;
}

export function formatCommitmentSchedule(commitment: CommitmentDraft): string {
  if (commitment.frequency === "once") {
    if (!commitment.dateKey) return "Data a definir";
    const header = formatDayHeader(commitment.dateKey);
    return `${header.weekdayShort} · ${header.dayMonth}`;
  }
  return formatWeekdays(commitment.weekdays);
}

export function formatWeekdays(weekdays: number[]): string {
  const sorted = [...weekdays].sort((a, b) => a - b);
  if (sorted.length === 5 && sorted.every((d, i) => d === i)) return "Seg a Sex";
  if (sorted.length === 7) return "Todos os dias";
  return sorted.map((d) => WEEKDAYS[d]?.short ?? "").join(", ");
}

export function formatMinutesLabel(minutes: number): string {
  if (minutes === 0) return "Sem intervalo";
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m === 0 ? `${h}h` : `${h}h${String(m).padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------
// Mensagens de erro da API em português
// ---------------------------------------------------------------------------

const FIELD_LABELS: Record<string, string> = {
  timezone: "Fuso horário",
  sleep_start: "Início do sono",
  sleep_end: "Fim do sono",
  buffer_minutes: "Intervalo entre blocos",
  max_block_minutes: "Duração máxima do bloco",
  min_block_minutes: "Duração mínima do bloco",
  consent_accepted: "Consentimento",
  label: "Nome do compromisso",
  start: "Início",
  end: "Término",
  kind: "Tipo",
};

function translatePydanticMessage(message: string): string {
  const rules: [RegExp, (m: RegExpMatchArray) => string][] = [
    [/greater than or equal to (\S+)/i, (m) => `deve ser maior ou igual a ${m[1]}`],
    [/less than or equal to (\S+)/i, (m) => `deve ser menor ou igual a ${m[1]}`],
    [/at least (\d+) character/i, (m) => `precisa ter pelo menos ${m[1]} caractere(s)`],
    [/at most (\d+) character/i, (m) => `pode ter no máximo ${m[1]} caracteres`],
    [/field required/i, () => "é obrigatório"],
    [/valid time/i, () => "precisa ser um horário válido"],
    [/valid datetime|timezone/i, () => "precisa ser uma data/hora válida com fuso"],
    [/extra inputs are not permitted/i, () => "não é aceito pela API"],
  ];
  for (const [pattern, build] of rules) {
    const match = message.match(pattern);
    if (match) return build(match);
  }
  return message; // validadores do backend já respondem em português
}

/** Converte erros 422 do FastAPI em frases legíveis ("Fim do sono: ..."). */
export function describeFieldErrors(fieldErrors: FieldError[]): string[] {
  return fieldErrors.map(({ field, message }) => {
    const leaf = field.split(".").pop() ?? "";
    const label = FIELD_LABELS[leaf];
    const text = translatePydanticMessage(message);
    return label ? `${label}: ${text}` : text.charAt(0).toUpperCase() + text.slice(1);
  });
}
