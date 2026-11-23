import { Skeleton } from "@/components/ui/skeleton";

/**
 * Skeleton genérico de página (cabeçalho + blocos de agenda).
 * Use enquanto a sessão ou os dados da API carregam.
 */
export function PageSkeleton({ label = "Carregando…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-4">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-7 w-48" />
      <Skeleton className="h-4 w-72 max-w-full" />
      <div className="mt-2 flex flex-col gap-3">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-4/5" />
      </div>
    </div>
  );
}

/** Lista de blocos de agenda em carregamento (timeline do Dashboard). */
export function ScheduleSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-3">
      <span className="sr-only">Carregando agenda…</span>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex items-center gap-3">
          <Skeleton className="h-4 w-12 shrink-0" />
          <Skeleton className="h-14 flex-1" />
        </div>
      ))}
    </div>
  );
}
