import type { Metadata } from "next";

import { ChatPanel } from "@/components/features/chat/chat-panel";

export const metadata: Metadata = { title: "Assistente" };

export default function ChatPage() {
  return <ChatPanel className="mx-auto w-full max-w-3xl px-4 py-6 lg:py-10" />;
}
