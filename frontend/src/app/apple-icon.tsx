import { ImageResponse } from "next/og";

import { VezoIconArt } from "@/components/brand/icon-art";

/** Ícone de "Adicionar à Tela de Início" no iOS (o iOS aplica a própria máscara). */
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(<VezoIconArt size={180} maskable />, size);
}
