"use client";

import { FileText, Image as ImageIcon, Mic } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import type { CitationItem } from "@/types/api";

function modality(item: CitationItem) {
  if (item.task_type === "audio") return { label: "Áudio", Icon: Mic };
  if (item.task_type === "ocr") return { label: "OCR", Icon: ImageIcon };
  return { label: item.source.toLowerCase().endsWith(".pdf") ? "PDF" : "Texto", Icon: FileText };
}

export function ChatCitations({ citations }: { citations: CitationItem[] }) {
  const [selected, setSelected] = useState<CitationItem | null>(null);
  if (citations.length === 0) return null;

  return (
    <>
      <div className="flex flex-wrap gap-2" aria-label="Fontes consultadas">
        {citations.map((citation, index) => {
          const { label, Icon } = modality(citation);
          return (
            <Button
              type="button" variant="outline" size="sm"
              key={`${citation.source_id}-${citation.source}-${index}`}
              onClick={() => setSelected(citation)}
              className="h-auto min-h-11 max-w-full whitespace-normal break-all border-accent bg-accent/40 px-2 py-2 text-left text-accent-foreground"
              aria-label={`Ver trecho da fonte ${citation.source_id}: ${citation.title || citation.source}`}
            >
              <Icon aria-hidden className="size-3.5" />
              <span>[{citation.source_id}: {citation.title || citation.source}]</span>
              <span className="text-xs opacity-70">{label}</span>
            </Button>
          );
        })}
      </div>
      <Dialog open={selected !== null} onOpenChange={(open) => { if (!open) setSelected(null); }}>
        <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="break-all">{selected?.title || selected?.source}</DialogTitle>
            <DialogDescription>Trecho literal recuperado da base documental.</DialogDescription>
          </DialogHeader>
          {selected ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{selected.source_id}</Badge>
                <Badge variant="secondary">{modality(selected).label}</Badge>
                {selected.page_or_time && <Badge variant="outline">{selected.page_or_time}</Badge>}
                <span className="font-mono text-xs text-muted-foreground">Similaridade: {selected.score.toFixed(2)}</span>
              </div>
              <blockquote className="max-h-[50dvh] overflow-auto whitespace-pre-wrap break-words border-l-4 border-primary bg-muted p-3 text-sm leading-relaxed">
                {selected.text}
              </blockquote>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
