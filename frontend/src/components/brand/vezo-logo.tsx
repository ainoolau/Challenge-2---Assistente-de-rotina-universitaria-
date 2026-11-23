import { cn } from "@/lib/utils";

/** Marca Vezo (símbolo + nome). Cores vêm dos tokens via `text-*` / `bg-*`. */
export function VezoLogo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span
        aria-hidden
        className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground"
      >
        <svg viewBox="0 0 24 24" className="size-5" fill="none">
          <path
            d="M4 5.5 L12 19 L20 5.5"
            stroke="currentColor"
            strokeWidth={3}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <span className="text-lg font-semibold tracking-tight text-foreground">Vezo</span>
    </span>
  );
}
