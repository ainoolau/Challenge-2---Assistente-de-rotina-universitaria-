"use client";

import { CalendarPlus, Check, Clock3, X } from "lucide-react";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, isApiError } from "@/lib/api";
import type { PlanningProposal } from "@/types/api";

type ActionState = "pending" | "confirmed" | "rejected";

function dateTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  }).format(date);
}

export function ChatProposal({ proposal, proposalId }: { proposal: PlanningProposal | null; proposalId: string | null }) {
  const [status, setStatus] = useState<ActionState>("pending");
  const [busy, setBusy] = useState<"confirm" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!proposal || !proposalId) return null;

  async function act(action: "confirm" | "reject") {
    if (!proposalId || busy || status !== "pending") return;
    setBusy(action);
    setError(null);
    try {
      if (action === "confirm") {
        await api.schedule.confirmProposal(proposalId);
        setStatus("confirmed");
        // A tela de rotina escuta este evento e recarrega a agenda do backend.
        window.dispatchEvent(new Event("vezo:schedule-updated"));
      } else {
        await api.schedule.rejectProposal(proposalId);
        setStatus("rejected");
      }
    } catch (cause) {
      setError(isApiError(cause) ? cause.message : "Não foi possível concluir a ação. Tente novamente.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section aria-label="Proposta de agenda" className="space-y-3 rounded-lg border-2 border-dashed border-slot-study-proposed bg-slot-study-proposed-bg p-3 text-slot-study-proposed-fg">
      <div className="flex flex-wrap items-center gap-2">
        <CalendarPlus aria-hidden className="size-4" />
        <h3 className="font-semibold">Proposta de agenda</h3>
        <Badge variant={status === "pending" ? "proposal" : "outline"}>
          {status === "pending" ? "Aguardando confirmação" : status === "confirmed" ? "Confirmada" : "Descartada"}
        </Badge>
      </div>
      <p className="text-sm">{proposal.diff_summary}</p>
      <p className="text-xs">{status === "pending" ? "Nenhuma alteração foi aplicada à sua agenda." : status === "confirmed" ? "Agenda atualizada após sua confirmação." : "A proposta não foi aplicada."}</p>
      <ul className="space-y-2" aria-label="Blocos de estudo propostos">
        {proposal.proposed_blocks.map((block, index) => (
          <li key={`${block.goal_id}-${block.start}-${index}`} className="rounded-md border border-dashed border-slot-study-proposed bg-card p-2 text-card-foreground">
            <div className="font-medium">{block.title}</div>
            <div className="mt-1 flex items-center gap-1 text-xs text-muted-foreground"><Clock3 aria-hidden className="size-3.5" />{dateTime(block.start)} – {dateTime(block.end)}</div>
          </li>
        ))}
      </ul>
      {proposal.unallocated.length > 0 && (
        <Alert variant="warning">
          <AlertDescription>
            <strong>Tempo não alocado:</strong>{" "}
            {proposal.unallocated.map((item) => `${item.goal_id}: ${item.remaining_minutes} min`).join("; ")}. Sono e compromissos fixos devem ser preservados.
          </AlertDescription>
        </Alert>
      )}
      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      {status === "pending" && (
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" onClick={() => void act("confirm")} disabled={busy !== null}>
            <Check aria-hidden />{busy === "confirm" ? "Confirmando..." : "Confirmar e aplicar"}
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => void act("reject")} disabled={busy !== null}>
            <X aria-hidden />{busy === "reject" ? "Descartando..." : "Descartar"}
          </Button>
        </div>
      )}
    </section>
  );
}
