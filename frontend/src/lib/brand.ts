/**
 * Constantes da marca Vezo para contextos que NÃO leem CSS variables
 * (manifest.webmanifest, <meta name="theme-color"> e ícones gerados via ImageResponse).
 *
 * Os valores espelham os primitivos de `src/styles/tokens.css` (TASK-F1-03 / #46).
 * Componentes React devem continuar usando apenas classes/tokens semânticos.
 */
export const BRAND = {
  name: "Vezo",
  shortName: "Vezo",
  description:
    "Assistente de rotina universitária: organize aulas, trabalho, estudo e sono protegido no seu ritmo.",
  tagline: "Sua rotina, no seu ritmo.",
  colors: {
    /** --vezo-ocean — primária (modo claro) */
    ocean: "#094D60",
    /** --vezo-turquoise — primária (modo escuro) */
    turquoise: "#25CBC1",
    /** --background (modo claro) */
    backgroundLight: "#F6FAFA",
    /** --vezo-ink-dark — --background (modo escuro) */
    backgroundDark: "#101C1C",
  },
} as const;
