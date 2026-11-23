import type { Metadata } from "next";

import { DashboardView } from "@/components/features/routine/dashboard-view";

export const metadata: Metadata = { title: "Rotina" };

export default function RotinaPage() {
  return <DashboardView />;
}
