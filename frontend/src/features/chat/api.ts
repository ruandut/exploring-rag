import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { RetrievedChunk } from "@/lib/socket";

import type { Turn } from "./conversation";

export type ConversationSummary = {
  id: number;
  title: string;
  agent_key: string;
  agent_name: string;
  message_count: number;
  updated_at: string;
};

type StoredMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  status: "done" | "cancelled" | "error";
  run_id: string;
  metadata: {
    thinking?: string;
    tool_calls?: { tool: string; args: Record<string, unknown> }[];
    retrieved?: RetrievedChunk[];
    model?: string;
    error?: string;
  };
};

export type ConversationDetail = ConversationSummary & { messages: StoredMessage[] };

export function useConversations() {
  return useQuery({
    queryKey: ["conversations"],
    queryFn: () => api<ConversationSummary[]>("/api/chat/conversations/"),
  });
}

export function fetchConversation(id: number) {
  return api<ConversationDetail>(`/api/chat/conversations/${id}/`);
}

/** Saved messages → the same Turn shape the live stream builds, so both render identically. */
export function toTurns(detail: ConversationDetail): Turn[] {
  return detail.messages.map((m) =>
    m.role === "user"
      ? { role: "user", text: m.content }
      : {
          role: "assistant",
          runId: m.run_id || null,
          agentId: detail.agent_key,
          thinking: m.metadata.thinking ?? "",
          toolCalls: m.metadata.tool_calls ?? [],
          retrieved: m.metadata.retrieved ?? [],
          text: m.content,
          status: m.status,
          error: m.metadata.error,
          model: m.metadata.model,
        },
  );
}
