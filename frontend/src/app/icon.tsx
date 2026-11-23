import { ImageResponse } from "next/og";

import { VezoIconArt } from "@/components/brand/icon-art";

/**
 * Ícones PWA gerados em build (PNG), sem versionar binários no repositório
 * (o .gitignore da raiz bloqueia *.png fora de data/samples).
 *
 * URLs: /icon/192, /icon/512 e /icon/maskable (área segura de 80% para Android).
 */
const ICONS = [
  { id: "192", size: 192, maskable: false },
  { id: "512", size: 512, maskable: false },
  { id: "maskable", size: 512, maskable: true },
] as const;

export function generateImageMetadata() {
  return ICONS.map(({ id, size }) => ({
    id,
    size: { width: size, height: size },
    contentType: "image/png",
  }));
}

export default async function Icon({ id }: { id: Promise<string | number> }) {
  const iconId = String(await id);
  const icon = ICONS.find((item) => item.id === iconId) ?? ICONS[1];
  return new ImageResponse(<VezoIconArt size={icon.size} maskable={icon.maskable} />, {
    width: icon.size,
    height: icon.size,
  });
}
