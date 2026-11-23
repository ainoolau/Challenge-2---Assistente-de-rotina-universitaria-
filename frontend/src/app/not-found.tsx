import { Compass } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/states/empty-state";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="px-4 py-6 lg:px-8 lg:py-8">
      <EmptyState
        icon={Compass}
        title="Página não encontrada"
        description="O endereço acessado não existe no Vezo."
        action={
          <Button asChild>
            <Link href="/">Voltar para a rotina</Link>
          </Button>
        }
      />
    </div>
  );
}
