/**
 * Contratos da API FastAPI do Vezo espelhados em TypeScript.
 *
 * Fontes de verdade (somente leitura): `src/api/schemas.py` e `src/core/schemas.py`.
 * Ao alterar um schema Pydantic, atualize este arquivo no mesmo PR.
 *
 * Convenções de serialização (Pydantic v2 → JSON):
 * - `datetime` → string ISO 8601 **com fuso explícito** (ex.: "2026-12-01T08:00:00-03:00").
 * - `time`     → string "HH:MM:SS" (ou "HH:MM"), sem fuso (usa o fuso da sessão).
 * - Todos os contratos usam `extra="forbid"`: não envie campos não listados aqui.
 */

/** ISO 8601 com offset obrigatório (o backend rejeita datetimes "naive"). */
export type IsoDateTime = string;
/** Horário local "HH:MM" ou "HH:MM:SS" no fuso IANA da sessão. */
export type LocalTime = string;

// ===========================================================================
// src/core/schemas.py
// ===========================================================================

export interface Interval {
  start: IsoDateTime;
  end: IsoDateTime;
}

export type ScheduleSlotKind = "sleep" | "work" | "class" | "commute" | "other";
export type ScheduleModality = "presencial" | "remoto" | "hibrido";

export interface ScheduleSlot extends Interval {
  slot_id?: string | null;
  label: string;
  kind?: ScheduleSlotKind;
  fixed?: boolean;
  modality?: ScheduleModality;
  allow_overlap?: boolean;
  buffer_before_minutes?: number;
  buffer_after_minutes?: number;
}

export interface StudyGoal {
  goal_id: string;
  title: string;
  /** 1 a 10080 minutos. */
  duration_minutes: number;
  deadline: IsoDateTime;
  /** 1 (baixa) a 5 (alta). */
  priority?: number;
}

export interface ProposedBlock extends Interval {
  goal_id: string;
  title: string;
}

export interface Unallocated {
  goal_id: string;
  remaining_minutes: number;
}

export interface PlanningProposal {
  proposed_blocks: ProposedBlock[];
  unallocated: Unallocated[];
  diff_summary: string;
  requires_confirmation: true;
}

export interface MovedBlock {
  goal_id: string;
  title: string;
  previous_start: IsoDateTime;
  previous_end: IsoDateTime;
  new_start: IsoDateTime;
  new_end: IsoDateTime;
  reason: string;
}

export interface ScheduleDiff {
  added: ProposedBlock[];
  removed: ProposedBlock[];
  moved: MovedBlock[];
  kept: ProposedBlock[];
}

export interface RebalanceProposal {
  proposed_blocks: ProposedBlock[];
  diff: ScheduleDiff;
  reasons: string[];
  unallocated: Unallocated[];
  input_conflicts: string[];
  diff_summary: string;
  requires_confirmation: true;
}

// ===========================================================================
// src/api/schemas.py
// ===========================================================================

export type ScheduleItemKind = ScheduleSlotKind | "study";

export interface HealthResponse {
  status: "ok";
  version: string;
  db_ok: boolean;
  qdrant_configured: boolean;
  llm_configured: boolean;
}

export interface SessionPreferences {
  timezone: string;
  sleep_start: LocalTime;
  sleep_end: LocalTime;
  buffer_minutes: number;
  max_block_minutes: number;
  min_block_minutes: number;
  consent_accepted: boolean;
  consent_timestamp: string | null;
}

export interface SessionCreateRequest {
  timezone?: string;
  sleep_start?: LocalTime;
  sleep_end?: LocalTime;
  /** 0 a 120. */
  buffer_minutes?: number;
  /** 15 a 240. */
  max_block_minutes?: number;
  /** 1 a 60. */
  min_block_minutes?: number;
  consent_accepted?: boolean;
}

/** Corpo de PUT/PATCH /preferences (todos os campos opcionais). */
export interface PreferencesUpdateRequest {
  timezone?: string | null;
  sleep_start?: LocalTime | null;
  sleep_end?: LocalTime | null;
  buffer_minutes?: number | null;
  max_block_minutes?: number | null;
  min_block_minutes?: number | null;
  consent_accepted?: boolean | null;
}

export interface SessionResponse {
  session_id: string;
  /** Só é devolvido na criação (POST /sessions). Nunca persista em localStorage. */
  session_token: string | null;
  schedule_version: number;
  preferences: SessionPreferences;
  created_at: string;
  auth_note: string;
}

export interface ScheduleItemCreate extends Interval {
  label: string;
  kind?: ScheduleItemKind;
  fixed?: boolean;
  modality?: ScheduleModality;
  allow_overlap?: boolean;
  goal_id?: string | null;
  buffer_before_minutes?: number;
  buffer_after_minutes?: number;
}

export interface ScheduleItemUpdate {
  start?: IsoDateTime | null;
  end?: IsoDateTime | null;
  label?: string | null;
  kind?: ScheduleItemKind | null;
  fixed?: boolean | null;
  modality?: ScheduleModality | null;
  allow_overlap?: boolean | null;
  goal_id?: string | null;
  buffer_before_minutes?: number | null;
  buffer_after_minutes?: number | null;
}

export interface ScheduleItemResponse extends Interval {
  item_id: string;
  label: string;
  kind: ScheduleItemKind;
  fixed: boolean;
  modality: ScheduleModality;
  allow_overlap: boolean;
  goal_id: string | null;
  buffer_before_minutes: number;
  buffer_after_minutes: number;
  created_at: string;
  updated_at: string;
}

export interface ScheduleListResponse {
  schedule_version: number;
  preferences: SessionPreferences;
  items: ScheduleItemResponse[];
  input_conflicts: string[];
  free_windows: Interval[];
}

/** Query string opcional de GET /schedule (informe os dois juntos). */
export interface ScheduleListQuery {
  horizon_start: IsoDateTime;
  horizon_end: IsoDateTime;
}

export interface OptimizeScheduleRequest {
  horizon: Interval;
  /** 1 a 50 metas. */
  study_goals: StudyGoal[];
  buffer_minutes?: number | null;
  max_block_minutes?: number | null;
  min_block_minutes?: number | null;
}

export interface ReallocateScheduleRequest {
  horizon: Interval;
  disruptions?: ScheduleSlot[];
  study_goals?: StudyGoal[];
  disruption_note?: string | null;
  buffer_minutes?: number | null;
  max_block_minutes?: number | null;
  min_block_minutes?: number | null;
}

export type ProposalType = "optimize" | "reallocate" | "chat";
export type ProposalStatus = "pending" | "confirmed" | "rejected";

export interface ScheduleProposalResponse {
  proposal_id: string;
  proposal_type: ProposalType;
  status: ProposalStatus;
  base_version: number;
  /** A agenda nunca é alterada sem confirmação explícita do usuário. */
  requires_confirmation: true;
  planning: PlanningProposal | null;
  rebalance: RebalanceProposal | null;
  input_conflicts: string[];
  created_at: string;
}

export interface ProposalActionResponse {
  proposal_id: string;
  status: "confirmed" | "rejected";
  schedule_version: number;
  applied_blocks: ProposedBlock[];
  items_count: number;
  message: string;
}

export interface DocumentUploadResponse {
  filename: string;
  chunks: number;
  unchanged: boolean;
}

export interface DocumentItem {
  filename: string;
  created_at: string | null;
}

export type ChatScope = "private" | "demo";

export interface ChatQueryRequest {
  scope?: ChatScope;
  /** 5 a 4000 caracteres. */
  question: string;
  horizon?: Interval | null;
  study_goals?: StudyGoal[];
  include_session_schedule?: boolean;
}

export interface CitationItem {
  source_id: string;
  source: string;
  title: string | null;
  page_or_time: string | null;
  text: string;
  score: number;
  task_type: string | null;
}

export interface ChatQueryResponse {
  run_id: string;
  status: "completed" | "abstained" | "error";
  abstained: boolean;
  answer: string;
  citations: CitationItem[];
  limitations: string[];
  gaps: string[];
  input_conflicts: string[];
  planning: PlanningProposal | null;
  proposal_id: string | null;
  requires_confirmation: true;
  llm_calls: number;
  total_latency_ms: number;
}

export interface ChatHistoryMessage {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  abstained: boolean | null;
  proposal_id: string | null;
  citations: CitationItem[];
  created_at: string;
}

// ===========================================================================
// Erros FastAPI
// ===========================================================================

/** Item de erro de validação Pydantic devolvido em `detail` (HTTP 422). */
export interface ValidationErrorItem {
  type: string;
  loc: (string | number)[];
  msg: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

/** Corpo padrão de erro do FastAPI (`HTTPException` / validação). */
export interface ApiErrorBody {
  detail: string | ValidationErrorItem[];
}
