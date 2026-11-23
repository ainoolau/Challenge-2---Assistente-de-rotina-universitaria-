import type { Metadata } from "next";

import { OnboardingView } from "@/components/features/onboarding/onboarding-view";

export const metadata: Metadata = { title: "Configurar rotina" };

export default function OnboardingPage() {
  return <OnboardingView />;
}
