import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: ReactNode;
  /** Ação principal orientativa (ex.: botão "Configurar rotina"). */
  action?: ReactNode;
  className?: string;
}

/** Estado vazio orientativo: explica o que falta e oferece o próximo passo. */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 rounded-lg border border-dashed bg-card px-6 py-10 text-center",
        className,
      )}
    >
      <Icon aria-hidden className="size-8 text-muted-foreground" strokeWidth={1.5} />
      <div className="flex max-w-sm flex-col gap-1">
        <h2 className="text-lg font-semibold text-card-foreground">{title}</h2>
        {description ? (
          <p className="text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
