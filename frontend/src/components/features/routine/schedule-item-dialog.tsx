"use client";

import { AlertTriangle, Lock, ShieldAlert, Trash2 } from "lucide-react";
import Link from "next/link";
import { useId, useState, type FormEvent } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api, isApiError } from "@/lib/api";
import type {
  ScheduleItemKind,
  ScheduleItemResponse,
  SessionPreferences,
} from "@/types/api";

import {
  EDITABLE_KINDS,
  KIND_LABELS,
  buildZonedIso,
  classifyConflictError,
  isoToDateKey,
  toLocalTimeHHMM,
} from "./schedule-utils";

export interface ScheduleItemDraft {
  dateKey: string;
  startTime: string;
  endTime: string;
  kind?: Exclude<ScheduleItemKind, "sleep">;
  fixed?: boolean;
}

interface ScheduleItemDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  preferences: SessionPreferences;
  editingItem: ScheduleItemResponse | null;
  initialDraft: ScheduleItemDraft;
  onSaved: (message: string) => void;
}

type PendingForceAction = "update" | "delete" | null;

export function ScheduleItemDialog({
  open,
  onOpenChange,
  preferences,
  editingItem,
  initialDraft,
  onSaved,
}: ScheduleItemDialogProps) {
  const instanceKey = editingItem
    ? `edit-${editingItem.item_id}-${editingItem.updated_at}`
    : `new-${initialDraft.dateKey}-${initialDraft.startTime}-${initialDraft.endTime}`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? (
        <ScheduleItemDialogBody
          key={instanceKey}
          onClose={() => onOpenChange(false)}
          preferences={preferences}
          editingItem={editingItem}
          initialDraft={initialDraft}
          onSaved={onSaved}
        />
      ) : null}
    </Dialog>
  );
}

function ScheduleItemDialogBody({
  onClose,
  preferences,
  editingItem,
  initialDraft,
  onSaved,
}: Omit<ScheduleItemDialogProps, "open" | "onOpenChange"> & { onClose: () => void }) {
  const formId = useId();
  const [label, setLabel] = useState(editingItem?.label ?? "");
  const [kind, setKind] = useState<Exclude<ScheduleItemKind, "sleep">>(
    editingItem
      ? editingItem.kind === "sleep"
        ? "other"
        : editingItem.kind
      : (initialDraft.kind ?? "class"),
  );
  const [dateKey, setDateKey] = useState(
    editingItem
      ? isoToDateKey(editingItem.start, preferences.timezone)
      : initialDraft.dateKey,
  );
  const [startTime, setStartTime] = useState(
    editingItem
      ? toLocalTimeHHMM(editingItem.start, preferences.timezone)
      : initialDraft.startTime,
  );
  const [endTime, setEndTime] = useState(
    editingItem
      ? toLocalTimeHHMM(editingItem.end, preferences.timezone)
      : initialDraft.endTime,
  );
  const [fixed, setFixed] = useState(editingItem ? editingItem.fixed : (initialDraft.fixed ?? true));
  const [bufferBefore, setBufferBefore] = useState(
    editingItem ? String(editingItem.buffer_before_minutes) : "0",
  );
  const [bufferAfter, setBufferAfter] = useState(
    editingItem ? String(editingItem.buffer_after_minutes) : "0",
  );

  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<ApiError | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [pendingForce, setPendingForce] = useState<PendingForceAction>(null);

  function validateLocally(): string | null {
    if (!label.trim()) return "Informe um título para o compromisso.";
    if (!dateKey) return "Selecione a data do compromisso.";
    if (!startTime || !endTime) return "Informe o horário de início e término.";
    if (endTime <= startTime) {
      return "O horário de término deve ser posterior ao horário de início.";
    }
    const before = Number(bufferBefore);
    const after = Number(bufferAfter);
    if (Number.isNaN(before) || before < 0 || before > 180) {
      return "Buffer anterior deve estar entre 0 e 180 minutos.";
    }
    if (Number.isNaN(after) || after < 0 || after > 180) {
      return "Buffer posterior deve estar entre 0 e 180 minutos.";
    }
    return null;
  }

  async function submitSave(forceFixed: boolean) {
    const validationMsg = validateLocally();
    if (validationMsg) {
      setLocalError(validationMsg);
      return;
    }

    setLocalError(null);
    setApiError(null);
    setSubmitting(true);

    const payload = {
      label: label.trim(),
      kind,
      start: buildZonedIso(dateKey, startTime, preferences.timezone),
      end: buildZonedIso(dateKey, endTime, preferences.timezone),
      fixed,
      buffer_before_minutes: Number(bufferBefore) || 0,
      buffer_after_minutes: Number(bufferAfter) || 0,
    };

    try {
      if (editingItem) {
        await api.schedule.update(editingItem.item_id, payload, { forceFixed });
        onSaved(`Compromisso "${payload.label}" atualizado.`);
      } else {
        await api.schedule.create(payload);
        onSaved(`Compromisso "${payload.label}" adicionado à agenda.`);
      }
      onClose();
    } catch (err) {
      const error = isApiError(err)
        ? err
        : new ApiError(0, "unknown", "Não foi possível salvar o compromisso.");
      setApiError(error);
      if (error.kind === "conflict" && classifyConflictError(error.message) === "fixed") {
        setPendingForce("update");
      } else {
        setPendingForce(null);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function submitDelete(forceFixed: boolean) {
    if (!editingItem) return;
    setLocalError(null);
    setApiError(null);
    setSubmitting(true);

    try {
      await api.schedule.remove(editingItem.item_id, { forceFixed });
      onSaved(`Compromisso "${editingItem.label}" removido da agenda.`);
      onClose();
    } catch (err) {
      const error = isApiError(err)
        ? err
        : new ApiError(0, "unknown", "Não foi possível remover o compromisso.");
      setApiError(error);
      if (error.kind === "conflict" && classifyConflictError(error.message) === "fixed") {
        setPendingForce("delete");
      } else {
        setPendingForce(null);
      }
    } finally {
      setSubmitting(false);
    }
  }

  function handleFormSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitSave(false);
  }

  const conflictKind =
    apiError?.kind === "conflict" ? classifyConflictError(apiError.message) : null;
  const fieldError = (name: string) =>
    apiError?.fieldErrors.find((item) => item.field.includes(name))?.message;

  const sleepStart = preferences.sleep_start.slice(0, 5);
  const sleepEnd = preferences.sleep_end.slice(0, 5);

  return (
    <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {editingItem ? "Editar compromisso" : "Novo compromisso"}
          </DialogTitle>
          <DialogDescription>
            Fuso da sessão: <span className="font-mono">{preferences.timezone}</span> · Sono
            protegido: <span className="font-mono">{sleepStart}–{sleepEnd}</span>.
          </DialogDescription>
        </DialogHeader>

        <form id={formId} onSubmit={handleFormSubmit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`${formId}-label`}>Título</Label>
            <Input
              id={`${formId}-label`}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Ex.: Aula de Econometria I"
              maxLength={200}
              aria-invalid={Boolean(fieldError("label") || (localError && !label.trim()))}
              required
            />
            {fieldError("label") ? (
              <p className="text-xs text-destructive-subtle-foreground">{fieldError("label")}</p>
            ) : null}
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${formId}-kind`}>Categoria</Label>
              <select
                id={`${formId}-kind`}
                value={kind}
                onChange={(e) => {
                  const nextKind = e.target.value as Exclude<ScheduleItemKind, "sleep">;
                  setKind(nextKind);
                  if (nextKind === "study") setFixed(false);
                }}
                className="h-11 w-full rounded-lg border border-input bg-card px-3 text-base text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                {EDITABLE_KINDS.map((k) => (
                  <option key={k} value={k}>
                    {KIND_LABELS[k]}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${formId}-date`}>Data</Label>
              <Input
                id={`${formId}-date`}
                type="date"
                value={dateKey}
                onChange={(e) => setDateKey(e.target.value)}
                aria-invalid={Boolean(fieldError("start"))}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${formId}-start`}>Início</Label>
              <Input
                id={`${formId}-start`}
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                aria-invalid={Boolean(fieldError("start"))}
                required
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${formId}-end`}>Término</Label>
              <Input
                id={`${formId}-end`}
                type="time"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                aria-invalid={Boolean(fieldError("end") || endTime <= startTime)}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${formId}-buf-before`}>Buffer antes (min)</Label>
              <Input
                id={`${formId}-buf-before`}
                type="number"
                min={0}
                max={180}
                value={bufferBefore}
                onChange={(e) => setBufferBefore(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${formId}-buf-after`}>Buffer depois (min)</Label>
              <Input
                id={`${formId}-buf-after`}
                type="number"
                min={0}
                max={180}
                value={bufferAfter}
                onChange={(e) => setBufferAfter(e.target.value)}
              />
            </div>
          </div>

          <label
            htmlFor={`${formId}-fixed`}
            className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm has-[:checked]:border-primary has-[:checked]:bg-accent"
          >
            <input
              id={`${formId}-fixed`}
              type="checkbox"
              checked={fixed}
              onChange={(e) => setFixed(e.target.checked)}
              className="mt-0.5 size-5 shrink-0 accent-primary"
            />
            <span>
              <strong>Compromisso fixo</strong> — o Vezo nunca move este horário ao otimizar ou
              rebalancear sua semana.
            </span>
          </label>

          {localError ? (
            <Alert variant="destructive">
              <AlertTriangle aria-hidden />
              <AlertTitle>Revise os campos</AlertTitle>
              <AlertDescription>{localError}</AlertDescription>
            </Alert>
          ) : null}

          {apiError && conflictKind === "sleep" ? (
            <Alert variant="destructive">
              <ShieldAlert aria-hidden />
              <AlertTitle>Bloqueado: sono protegido ({sleepStart}–{sleepEnd})</AlertTitle>
              <AlertDescription className="flex flex-col gap-2">
                <span>{apiError.message}</span>
                <span>
                  Ajuste o horário do compromisso ou edite sua janela de descanso em{" "}
                  <Link href="/onboarding" className="font-semibold underline underline-offset-4">
                    Preferências
                  </Link>
                  .
                </span>
              </AlertDescription>
            </Alert>
          ) : null}

          {apiError && conflictKind === "fixed" && pendingForce ? (
            <Alert variant="warning">
              <Lock aria-hidden />
              <AlertTitle>Confirmação dupla — compromisso fixo protegido</AlertTitle>
              <AlertDescription className="flex flex-col gap-3">
                <span>
                  {apiError.message} Confirme explicitamente abaixo se realmente deseja{" "}
                  {pendingForce === "delete" ? "remover" : "alterar"} este compromisso fixo.
                </span>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="destructive"
                    size="sm"
                    disabled={submitting}
                    onClick={() =>
                      pendingForce === "delete"
                        ? void submitDelete(true)
                        : void submitSave(true)
                    }
                  >
                    {pendingForce === "delete"
                      ? "Confirmar remoção de item fixo"
                      : "Confirmar alteração de item fixo"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setPendingForce(null);
                      setApiError(null);
                    }}
                  >
                    Cancelar
                  </Button>
                </div>
              </AlertDescription>
            </Alert>
          ) : null}

          {apiError && conflictKind !== "sleep" && !(conflictKind === "fixed" && pendingForce) ? (
            <Alert variant="destructive">
              <AlertTriangle aria-hidden />
              <AlertTitle>
                {apiError.kind === "validation"
                  ? "Erro de validação (422)"
                  : "Não foi possível concluir"}
              </AlertTitle>
              <AlertDescription>{apiError.message}</AlertDescription>
            </Alert>
          ) : null}
        </form>

        <DialogFooter className="sm:justify-between">
          {editingItem ? (
            <Button
              type="button"
              variant="destructive"
              disabled={submitting}
              onClick={() => void submitDelete(false)}
            >
              <Trash2 aria-hidden />
              Remover
            </Button>
          ) : (
            <span />
          )}

          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button
              type="button"
              variant="outline"
              disabled={submitting}
              onClick={onClose}
            >
              Cancelar
            </Button>
            <Button type="submit" form={formId} disabled={submitting}>
              {submitting
                ? "Salvando…"
                : editingItem
                  ? "Salvar alterações"
                  : "Adicionar compromisso"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
  );
}
