"use client";

import { RotateCw, TriangleAlert } from "lucide-react";

import { EmptyState } from "@/components/states/empty-state";
import { Button } from "@/components/ui/button";

/**
 * Boundary de erro inesperado de renderização. Não exibe `error.message`
 * para evitar vazar detalhes internos; falhas da API usam <ErrorState />.
 */
export default function RouteError({ retry }: { error: unknown; retry: () => void }) {
  return (
    <div className="px-4 py-6 lg:px-8 lg:py-8">
      <EmptyState
        icon={TriangleAlert}
        title="Não foi possível carregar esta tela"
        description="Tente novamente. Se o problema continuar, volte mais tarde."
        action={
          <Button onClick={() => retry()}>
            <RotateCw aria-hidden />
            Tentar novamente
          </Button>
        }
      />
    </div>
  );
}
