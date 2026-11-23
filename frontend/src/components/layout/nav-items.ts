import { CalendarDays, MessageSquareText, SlidersHorizontal, type LucideIcon } from "lucide-react";

export interface NavItem {
  href: "/" | "/chat" | "/onboarding";
  label: string;
  /** Rótulo descritivo para leitores de tela. */
  description: string;
  icon: LucideIcon;
}

/** As 3 abas principais do PWA (DESIGN.md §4.1). */
export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/", label: "Rotina", description: "Agenda de hoje, semana e mês", icon: CalendarDays },
  { href: "/chat", label: "Assistente", description: "Chat com o assistente Vezo", icon: MessageSquareText },
  { href: "/onboarding", label: "Ajustes", description: "Rotina, sono e preferências", icon: SlidersHorizontal },
];

export function isActive(pathname: string, href: NavItem["href"]): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}
