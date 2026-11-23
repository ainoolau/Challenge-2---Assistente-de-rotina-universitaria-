import { PageSkeleton } from "@/components/states/loading-state";

/** Fallback de navegação entre rotas (streaming). */
export default function Loading() {
  return (
    <div className="px-4 py-6 lg:px-8 lg:py-8">
      <PageSkeleton />
    </div>
  );
}
