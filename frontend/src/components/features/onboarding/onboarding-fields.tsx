"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Mesmo visual do `Input` (shadcn) para o `<select>` nativo — acessível e sem JS extra. */
export const selectClassName =
  "h-11 w-full min-w-0 rounded-lg border border-input bg-card px-3 text-base outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 dark:bg-input/30";

/** Mensagem inline de erro de campo (DESIGN.md §4.2 — estado 422). */
export function FieldMessage({ id, children }: { id: string; children?: ReactNode }) {
  if (!children) return null;
  return (
    <p id={id} className="text-sm text-destructive-subtle-foreground">
      {children}
    </p>
  );
}

interface ChoiceOption<T extends string | number> {
  value: T;
  label: string;
  hint?: string;
  icon?: ReactNode;
}

/**
 * Grupo de opções em "chips" com semântica de rádio nativa.
 * Cada opção tem alvo de toque >= 44px e foco visível.
 */
export function ChoiceGroup<T extends string | number>({
  name,
  legend,
  description,
  options,
  value,
  onChange,
  error,
  errorId,
  columns = "auto",
}: {
  name: string;
  legend: string;
  description?: string;
  options: readonly ChoiceOption<T>[];
  value: T;
  onChange: (value: T) => void;
  error?: string;
  errorId: string;
  columns?: "auto" | "two";
}) {
  const descriptionId = description ? `${errorId}-desc` : undefined;
  return (
    <fieldset
      className="flex flex-col gap-2"
      aria-describedby={[descriptionId, error ? errorId : undefined].filter(Boolean).join(" ") || undefined}
    >
      <legend className="mb-1 text-sm font-medium">{legend}</legend>
      {description ? (
        <p id={descriptionId} className="-mt-1 text-sm text-muted-foreground">
          {description}
        </p>
      ) : null}
      <div
        className={cn(
          "grid gap-2",
          columns === "two" ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-[repeat(auto-fill,minmax(5.5rem,1fr))]",
        )}
      >
        {options.map((option) => {
          const checked = option.value === value;
          return (
            <label
              key={String(option.value)}
              className={cn(
                "flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm transition-colors",
                "has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50 has-[:focus-visible]:border-ring",
                checked
                  ? "border-primary bg-accent text-accent-foreground"
                  : "border-border hover:bg-muted",
              )}
            >
              <input
                type="radio"
                name={name}
                className="sr-only"
                checked={checked}
                onChange={() => onChange(option.value)}
              />
              {option.icon ? <span aria-hidden className="shrink-0">{option.icon}</span> : null}
              <span className="flex flex-col">
                <span className="font-medium">{option.label}</span>
                {option.hint ? (
                  <span className={cn("text-xs", checked ? "text-accent-foreground" : "text-muted-foreground")}>
                    {option.hint}
                  </span>
                ) : null}
              </span>
            </label>
          );
        })}
      </div>
      <FieldMessage id={errorId}>{error}</FieldMessage>
    </fieldset>
  );
}
