import type {
  Interval,
  IsoDateTime,
  ProposedBlock,
  ScheduleItemKind,
  ScheduleItemResponse,
} from "@/types/api";

export type RoutineViewMode = "hoje" | "semana" | "mes";

export type ConflictKind = "sleep" | "fixed" | "version" | "other";

export type DayLoadLevel = "leve" | "moderada" | "intensa" | "sobrecarga";

export const KIND_LABELS: Record<ScheduleItemKind, string> = {
  class: "Aula",
  work: "Trabalho / Residência",
  commute: "Deslocamento",
  study: "Estudo",
  sleep: "Sono protegido",
  other: "Outro",
};

export const EDITABLE_KINDS: readonly Exclude<ScheduleItemKind, "sleep">[] = [
  "class",
  "work",
  "commute",
  "study",
  "other",
] as const;

/** Formata um número inteiro com 2 dígitos. */
function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** Retorna "YYYY-MM-DD" de um Date no fuso IANA informado. */
export function toDateKey(date: Date, timeZone: string): string {
  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(date);
    const year = parts.find((p) => p.type === "year")?.value ?? "2026";
    const month = parts.find((p) => p.type === "month")?.value ?? "01";
    const day = parts.find((p) => p.type === "day")?.value ?? "01";
    return `${year}-${month}-${day}`;
  } catch {
    return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
  }
}

/** Retorna "HH:MM" de uma string ISO 8601 no fuso IANA informado. */
export function toLocalTimeHHMM(iso: IsoDateTime, timeZone: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso.slice(11, 16);
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      timeZone,
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date);
  } catch {
    return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
  }
}

/** Retorna "YYYY-MM-DD" de uma string ISO 8601 no fuso IANA informado. */
export function isoToDateKey(iso: IsoDateTime, timeZone: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso.slice(0, 10);
  return toDateKey(date, timeZone);
}

/** Adiciona N dias a uma chave "YYYY-MM-DD" (aritmética civil UTC sem DST drift). */
export function addDaysToKey(dateKey: string, days: number): string {
  const [y, m, d] = dateKey.split("-").map(Number);
  const utc = new Date(Date.UTC(y, (m ?? 1) - 1, (d ?? 1) + days));
  return `${utc.getUTCFullYear()}-${pad2(utc.getUTCMonth() + 1)}-${pad2(utc.getUTCDate())}`;
}

/** Retorna a segunda-feira da semana que contém `dateKey`. */
export function startOfWeekKey(dateKey: string): string {
  const [y, m, d] = dateKey.split("-").map(Number);
  const utc = new Date(Date.UTC(y, (m ?? 1) - 1, d ?? 1));
  const day = utc.getUTCDay(); // 0=dom, 1=seg...
  const diffToMonday = day === 0 ? -6 : 1 - day;
  return addDaysToKey(dateKey, diffToMonday);
}

/** Retorna os 7 dateKeys da semana (segunda a domingo). */
export function getWeekKeys(anchorDateKey: string): string[] {
  const monday = startOfWeekKey(anchorDateKey);
  return Array.from({ length: 7 }, (_, i) => addDaysToKey(monday, i));
}

/** Retorna a grade do mês (35 ou 42 células iniciando na segunda-feira). */
export function getMonthGridKeys(anchorDateKey: string): {
  monthLabel: string;
  currentMonthPrefix: string;
  days: string[];
} {
  const [y, m] = anchorDateKey.split("-").map(Number);
  const year = y ?? 2026;
  const month = m ?? 1;
  const firstOfMonth = `${year}-${pad2(month)}-01`;
  const gridStart = startOfWeekKey(firstOfMonth);
  const lastDayOfMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const lastOfMonth = `${year}-${pad2(month)}-${pad2(lastDayOfMonth)}`;
  const lastWeekStart = startOfWeekKey(lastOfMonth);
  const gridEnd = addDaysToKey(lastWeekStart, 6);

  const days: string[] = [];
  let cursor = gridStart;
  while (cursor <= gridEnd && days.length < 42) {
    days.push(cursor);
    cursor = addDaysToKey(cursor, 1);
  }

  const labelDate = new Date(Date.UTC(year, month - 1, 15));
  const monthLabel = new Intl.DateTimeFormat("pt-BR", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(labelDate);

  return {
    monthLabel,
    currentMonthPrefix: `${year}-${pad2(month)}`,
    days,
  };
}

/**
 * Calcula o offset IANA ("±HH:MM") para uma data/hora civil em `timeZone`.
 * Garante que todos os datetimes enviados ao FastAPI tenham fuso explícito.
 */
function resolveTimeZoneOffset(dateKey: string, timeHHMM: string, timeZone: string): string {
  const [y, m, d] = dateKey.split("-").map(Number);
  const [hh, mm] = timeHHMM.split(":").map(Number);
  const approxUtc = new Date(Date.UTC(y ?? 2026, (m ?? 1) - 1, d ?? 1, hh ?? 0, mm ?? 0));

  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    }).formatToParts(approxUtc);

    const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
    const asUtc = Date.UTC(
      get("year"),
      get("month") - 1,
      get("day"),
      get("hour"),
      get("minute"),
      get("second"),
    );
    const offsetMinutes = Math.round((asUtc - approxUtc.getTime()) / 60000);
    const sign = offsetMinutes >= 0 ? "+" : "-";
    const abs = Math.abs(offsetMinutes);
    return `${sign}${pad2(Math.floor(abs / 60))}:${pad2(abs % 60)}`;
  } catch {
    return "-03:00";
  }
}

/** Constrói um IsoDateTime com offset explícito a partir de data civil e hora local. */
export function buildZonedIso(dateKey: string, timeHHMM: string, timeZone: string): IsoDateTime {
  const cleanTime = timeHHMM.length === 5 ? `${timeHHMM}:00` : timeHHMM.slice(0, 8);
  const offset = resolveTimeZoneOffset(dateKey, cleanTime.slice(0, 5), timeZone);
  return `${dateKey}T${cleanTime}${offset}`;
}

/** Constrói o intervalo de horizonte (<= 14 dias) para consulta de free_windows / planejamento. */
export function buildHorizonForWeek(weekKeys: string[], timeZone: string): Interval {
  const startKey = weekKeys[0];
  const endNextKey = addDaysToKey(weekKeys[weekKeys.length - 1], 1);
  return {
    start: buildZonedIso(startKey, "00:00", timeZone),
    end: buildZonedIso(endNextKey, "00:00", timeZone),
  };
}

export function buildHorizonForDay(dateKey: string, timeZone: string): Interval {
  return {
    start: buildZonedIso(dateKey, "00:00", timeZone),
    end: buildZonedIso(addDaysToKey(dateKey, 1), "00:00", timeZone),
  };
}

/** Formata data curta para cabeçalhos de coluna (ex.: "Seg · 23/11"). */
export function formatDayHeader(dateKey: string): {
  weekdayShort: string;
  dayNumber: string;
  dayMonth: string;
  fullLabel: string;
} {
  const [y, m, d] = dateKey.split("-").map(Number);
  const utc = new Date(Date.UTC(y ?? 2026, (m ?? 1) - 1, d ?? 1, 12));
  const weekdayShort = new Intl.DateTimeFormat("pt-BR", {
    weekday: "short",
    timeZone: "UTC",
  })
    .format(utc)
    .replace(/\.$/, "");
  const fullLabel = new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(utc);
  return {
    weekdayShort,
    dayNumber: pad2(d ?? 1),
    dayMonth: `${pad2(d ?? 1)}/${pad2(m ?? 1)}`,
    fullLabel,
  };
}

export function formatShortDateTime(iso: IsoDateTime, timeZone: string): string {
  const key = isoToDateKey(iso, timeZone);
  const { weekdayShort, dayMonth } = formatDayHeader(key);
  return `${weekdayShort} ${dayMonth} · ${toLocalTimeHHMM(iso, timeZone)}`;
}

/** Duração em minutos entre dois timestamps ISO. */
export function durationMinutes(start: IsoDateTime, end: IsoDateTime): number {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  return Math.max(0, Math.round(ms / 60000));
}

export function formatMinutes(totalMinutes: number): string {
  if (totalMinutes < 60) return `${totalMinutes} min`;
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return m === 0 ? `${h}h` : `${h}h${pad2(m)}`;
}

/** Classifica a carga diária conforme DESIGN.md §4.2 (Leve / Moderada / Intensa / Sobrecarga). */
export function getDayLoad(totalMinutes: number): {
  level: DayLoadLevel;
  label: string;
  badgeVariant: "success" | "secondary" | "warning" | "destructive";
} {
  if (totalMinutes <= 300) {
    return { level: "leve", label: `Leve · ${formatMinutes(totalMinutes)}`, badgeVariant: "success" };
  }
  if (totalMinutes <= 480) {
    return {
      level: "moderada",
      label: `Moderada · ${formatMinutes(totalMinutes)}`,
      badgeVariant: "secondary",
    };
  }
  if (totalMinutes <= 600) {
    return {
      level: "intensa",
      label: `Intensa · ${formatMinutes(totalMinutes)}`,
      badgeVariant: "warning",
    };
  }
  return {
    level: "sobrecarga",
    label: `Sobrecarga · ${formatMinutes(totalMinutes)}`,
    badgeVariant: "destructive",
  };
}

/** Identifica a causa exata de um HTTP 409 devolvido pelo backend FastAPI. */
export function classifyConflictError(message: string): ConflictKind {
  const lower = message.toLowerCase();
  if (lower.includes("sono")) return "sleep";
  if (lower.includes("fixo") || lower.includes("protegido bloqueado")) return "fixed";
  if (lower.includes("versão") || lower.includes("alterada") || lower.includes("defasad")) {
    return "version";
  }
  return "other";
}

/** Verifica se um item persistido está citado em algum conflito pré-existente. */
export function itemHasConflict(item: ScheduleItemResponse, conflicts: string[]): boolean {
  if (conflicts.length === 0 || !item.fixed) return false;
  return conflicts.some((msg) => msg.includes(item.label));
}

/** Agrupa itens, propostas e janelas livres por dateKey no fuso da sessão. */
export function groupByDateKey<T extends Interval>(
  list: T[],
  timeZone: string,
): Record<string, T[]> {
  const map: Record<string, T[]> = {};
  for (const entry of list) {
    const key = isoToDateKey(entry.start, timeZone);
    if (!map[key]) map[key] = [];
    map[key].push(entry);
  }
  for (const key of Object.keys(map)) {
    map[key].sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
  }
  return map;
}

/** Retorna blocos propostos ativos (seja de optimize ou de reallocate). */
export function extractProposedBlocks(
  planningBlocks: ProposedBlock[] | undefined,
  rebalanceBlocks: ProposedBlock[] | undefined,
): ProposedBlock[] {
  return rebalanceBlocks ?? planningBlocks ?? [];
}
