import { BRAND } from "@/lib/brand";

/** Arte do ícone: "V" em Turquesa sobre Azul-Oceano, sem gradientes ou brilho. */
export function VezoIconArt({ size, maskable }: { size: number; maskable: boolean }) {
  // Ícones "maskable" ocupam o quadrado todo; os comuns têm cantos arredondados.
  const radius = maskable ? 0 : Math.round(size * 0.22);
  const glyph = Math.round(size * (maskable ? 0.46 : 0.58));
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: BRAND.colors.ocean,
        borderRadius: radius,
      }}
    >
      <svg width={glyph} height={glyph} viewBox="0 0 24 24" fill="none">
        <path
          d="M4 5.5 L12 19 L20 5.5"
          stroke={BRAND.colors.turquoise}
          strokeWidth={3.2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}
